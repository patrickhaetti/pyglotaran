"""Tests for glotaran/utils/io.py"""
from __future__ import annotations

import html
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from IPython.core.formatters import format_display_data

from glotaran.io import save_dataset
from glotaran.utils.io import DatasetMapping
from glotaran.utils.io import load_datasets
from glotaran.utils.io import relative_posix_path
from glotaran.utils.io import safe_parameters_fillna
from glotaran.utils.io import safe_parameters_replace


@pytest.fixture
def ds_mapping() -> DatasetMapping:
    """Dummy mapping for testing."""
    ds_mapping = DatasetMapping()

    ds_mapping["ds1"] = xr.DataArray([1, 2]).to_dataset(name="data")
    ds_mapping["ds2"] = xr.DataArray([3, 4]).to_dataset(name="data")
    return ds_mapping


@pytest.fixture
def dummy_datasets(tmp_path: Path) -> tuple[Path, xr.Dataset, xr.Dataset]:
    """Dummy files for testing."""
    ds1 = xr.DataArray([1, 2]).to_dataset(name="data")
    ds2 = xr.DataArray([3, 4]).to_dataset(name="data")
    save_dataset(ds1, tmp_path / "ds1_file.nc")
    save_dataset(ds2, tmp_path / "ds2_file.nc")
    return tmp_path, ds1, ds2


def test_dataset_mapping(ds_mapping: DatasetMapping):
    """Basic mapping functionality of ``DatasetMapping``."""

    assert "ds1" in ds_mapping
    assert "ds2" in ds_mapping
    assert len(ds_mapping) == 2

    assert repr(ds_mapping) == "{'ds1': <xarray.Dataset>, 'ds2': <xarray.Dataset>}"

    for ds_name, expected_ds_name in zip(ds_mapping, ["ds1", "ds2"]):
        assert ds_name == expected_ds_name

    del ds_mapping["ds1"]

    assert "ds1" not in ds_mapping
    assert "ds2" in ds_mapping
    assert len(ds_mapping) == 1

    assert repr(ds_mapping) == "{'ds2': <xarray.Dataset>}"


def test_dataset_mapping_ipython_render(ds_mapping: DatasetMapping):
    """Renders as html in an ipython context."""

    rendered_result = format_display_data(ds_mapping)[0]

    assert "text/html" in rendered_result
    assert html.unescape(rendered_result["text/html"]).startswith(
        "<pre>{'ds1': <xarray.Dataset>, 'ds2': <xarray.Dataset>}</pre>"
        "\n<details><summary>ds1</summary>"
    )
    assert rendered_result["text/plain"] == repr(ds_mapping)


def test_load_datasets_single_dataset(dummy_datasets: tuple[Path, xr.Dataset, xr.Dataset]):
    """Functionality of ``load_datasets`` with a single dataset of all supported types."""
    tmp_path, ds1, _ = dummy_datasets
    expected_source_path = (tmp_path / "ds1_file.nc").as_posix()

    str_result = load_datasets((tmp_path / "ds1_file.nc").as_posix())

    assert "ds1_file" in str_result
    assert np.all(str_result["ds1_file"].data == ds1.data)
    assert str_result["ds1_file"].source_path == expected_source_path
    assert str_result.source_path["ds1_file"] == expected_source_path

    path_result = load_datasets(tmp_path / "ds1_file.nc")

    assert "ds1_file" in path_result
    assert np.all(path_result["ds1_file"].data == ds1.data)
    assert path_result["ds1_file"].source_path == expected_source_path
    assert path_result.source_path["ds1_file"] == expected_source_path

    dataset_result = load_datasets(ds1)

    assert "ds1_file" in dataset_result
    assert np.all(dataset_result["ds1_file"].data == ds1.data)
    assert dataset_result["ds1_file"].source_path == expected_source_path
    assert dataset_result.source_path["ds1_file"] == expected_source_path

    dataarray_result = load_datasets(xr.DataArray([1, 2]))

    assert "dataset_1" in dataarray_result
    assert np.all(dataarray_result["dataset_1"].data == ds1.data)
    assert dataarray_result["dataset_1"].source_path == "dataset_1.nc"
    assert dataarray_result.source_path["dataset_1"] == "dataset_1.nc"

    pure_dataset_result = load_datasets(xr.DataArray([1, 2]).to_dataset(name="data"))

    assert "dataset_1" in pure_dataset_result
    assert np.all(pure_dataset_result["dataset_1"].data == ds1.data)
    assert pure_dataset_result["dataset_1"].source_path == "dataset_1.nc"
    assert pure_dataset_result.source_path["dataset_1"] == "dataset_1.nc"


def test_load_datasets_sequence(dummy_datasets: tuple[Path, xr.Dataset, xr.Dataset]):
    """Functionality of ``load_datasets`` with a sequence."""
    tmp_path, ds1, ds2 = dummy_datasets

    result = load_datasets([tmp_path / "ds1_file.nc", tmp_path / "ds2_file.nc"])

    assert "ds1_file" in result
    assert np.all(result["ds1_file"].data == ds1.data)
    assert result["ds1_file"].source_path == (tmp_path / "ds1_file.nc").as_posix()
    assert result.source_path["ds1_file"] == (tmp_path / "ds1_file.nc").as_posix()

    assert "ds2_file" in result
    assert np.all(result["ds2_file"].data == ds2.data)
    assert result["ds2_file"].source_path == (tmp_path / "ds2_file.nc").as_posix()
    assert result.source_path["ds2_file"] == (tmp_path / "ds2_file.nc").as_posix()


def test_load_datasets_mapping(dummy_datasets: tuple[Path, xr.Dataset, xr.Dataset]):
    """Functionality of ``load_datasets`` with a mapping."""
    tmp_path, ds1, ds2 = dummy_datasets

    result = load_datasets({"ds1": tmp_path / "ds1_file.nc", "ds2": tmp_path / "ds2_file.nc"})

    assert "ds1" in result
    assert np.all(result["ds1"].data == ds1.data)
    assert result["ds1"].source_path == (tmp_path / "ds1_file.nc").as_posix()
    assert result.source_path["ds1"] == (tmp_path / "ds1_file.nc").as_posix()

    assert "ds2" in result
    assert np.all(result["ds2"].data == ds2.data)
    assert result["ds2"].source_path == (tmp_path / "ds2_file.nc").as_posix()
    assert result.source_path["ds2"] == (tmp_path / "ds2_file.nc").as_posix()


def test_load_datasets_wrong_type():
    """Raise TypeError for not supported type"""
    with pytest.raises(
        TypeError,
        match=(
            r"Type 'int' for 'dataset_mappable' of value "
            r"'1' is not supported\."
            r"\nSupported types are:\n"
        ),
    ):
        load_datasets(1)


@pytest.mark.parametrize("rel_file_path", ("file.txt", "folder/file.txt"))
def test_relative_posix_path(tmp_path: Path, rel_file_path: str):
    """All possible permutation for the input values."""
    full_path = tmp_path / rel_file_path

    result_str = relative_posix_path(str(full_path))

    assert result_str == full_path.as_posix()

    result_path = relative_posix_path(full_path)

    assert result_path == full_path.as_posix()

    rel_result_str = relative_posix_path(str(full_path), tmp_path)

    assert rel_result_str == rel_file_path

    rel_result_path = relative_posix_path(full_path, str(tmp_path))

    assert rel_result_path == rel_file_path

    rel_result_no_coomon = relative_posix_path(
        (tmp_path / f"../{rel_file_path}").resolve().as_posix(), str(tmp_path)
    )

    assert rel_result_no_coomon == f"../{rel_file_path}"


@pytest.mark.skipif(not sys.platform.startswith("win32"), reason="Only needed for Windows")
def test_relative_posix_path_windows_diff_drives():
    """os.path.relpath doesn't cause crash when files are on different drives."""

    source_path = "D:\\data\\data_file.txt"
    result = relative_posix_path(source_path, "C:\\result_path")

    assert result == Path(source_path).as_posix()


def test_safe_parameters_fillna():
    """compare dataframes. df with values replaced by function and
    df2 with expected values."""

    # create df with integers and NaN
    df = pd.DataFrame
    data = [[1, np.nan, np.nan], [431, -4, 45], [2, np.nan, np.nan]]
    df = pd.DataFrame(data, columns=["test1", "minimum", "maximum"])

    # run test_safe_parameters_fillna function to replace values
    safe_parameters_fillna(df, "minimum", -np.inf)
    safe_parameters_fillna(df, "maximum", np.inf)

    # create df2 with expected values after function ran over df
    data2 = [[1, -np.inf, np.inf], [431, -4, 45], [2, -np.inf, np.inf]]
    df2 = pd.DataFrame(data2, columns=["test1", "minimum", "maximum"])

    # df and df2 should be equal
    assert np.all(df == df2)


def test_safe_parameters_replace():
    """compare dataframes. df with values replaced by function and
    df2 with expected values."""

    # create df with integers and np.inf
    data = [[1, -np.inf, np.inf], [431, -4, 45], [2, -np.inf, np.inf]]
    df = pd.DataFrame(data, columns=["test1", "minimum", "maximum"])

    # run safe_parameters_replace function to replace values
    safe_parameters_replace(df, "minimum", -np.inf, "")
    safe_parameters_replace(df, "maximum", np.inf, "")

    # create df2 with expected values after function ran over df
    data2 = [[1, "", ""], [431, -4, 45], [2, "", ""]]
    df2 = pd.DataFrame(data2, columns=["test1", "minimum", "maximum"])

    # df and df2 should be equal
    assert np.all(df == df2)
