from __future__ import annotations

import pathlib

import yaml

from glotaran.deprecation.modules.builtin_io_yml import model_spec_deprecations
from glotaran.io import ProjectIoInterface
from glotaran.io import register_project_io
from glotaran.model import Model
from glotaran.model import get_megacomplex
from glotaran.parameter import ParameterGroup
from glotaran.project import Result
from glotaran.project import Scheme
from glotaran.project.dataclasses import asdict
from glotaran.project.dataclasses import fromdict
from glotaran.utils.sanitize import sanitize_yaml


@register_project_io(["yml", "yaml", "yml_str"])
class YmlProjectIo(ProjectIoInterface):
    def load_model(self, file_name: str) -> Model:
        """parse_yaml_file reads the given file and parses its content as YML.

        Parameters
        ----------
        filename : str
            filename is the of the file to parse.

        Returns
        -------
        Model
            The content of the file as dictionary.
        """

        spec = self._load_yml(file_name)

        model_spec_deprecations(spec)

        spec = sanitize_yaml(spec)

        default_megacomplex = spec.get("default-megacomplex")

        if default_megacomplex is None and any(
            "type" not in m for m in spec["megacomplex"].values()
        ):
            raise ValueError(
                "Default megacomplex is not defined in model and "
                "at least one megacomplex does not have a type."
            )

        if "megacomplex" not in spec:
            raise ValueError("No megacomplex defined in model")

        megacomplex_types = {
            m["type"]: get_megacomplex(m["type"])
            for m in spec["megacomplex"].values()
            if "type" in m
        }
        if default_megacomplex is not None:
            megacomplex_types[default_megacomplex] = get_megacomplex(default_megacomplex)
            del spec["default-megacomplex"]

        return Model.from_dict(
            spec, megacomplex_types=megacomplex_types, default_megacomplex_type=default_megacomplex
        )

    def load_result_file(self, file_name: str) -> Result:
        """Create a :class:`Result` instance from the specs defined in a file.

        Parameters
        ----------
        file_name : str | PathLike[str]
            Path containing the result data.

        Returns
        -------
        Result
            :class:`Result` instance created from the saved format.
        """
        spec = self._load_yml(file_name)
        return fromdict(Result, spec)

    def load_parameters(self, file_name: str) -> ParameterGroup:
        """Create a ParameterGroup instance from the specs defined in a file.

        Parameters
        ----------
        file_name : str
            File containing the parameter specs.

        Returns
        -------
        ParameterGroup
            ParameterGroup instance created from the file.
        """

        spec = self._load_yml(file_name)

        if isinstance(spec, list):
            return ParameterGroup.from_list(spec)
        else:
            return ParameterGroup.from_dict(spec)

    def load_scheme(self, file_name: str) -> Scheme:
        spec = self._load_yml(file_name)
        file_path = pathlib.Path(file_name)
        return fromdict(Scheme, spec, folder=file_path.parent)

    def save_scheme(self, scheme: Scheme, file_name: str):
        file_name = pathlib.Path(file_name)
        scheme_dict = asdict(scheme)
        _write_dict(file_name, scheme_dict)

    def save_model(self, model: Model, file_name: str):
        """Save a Model instance to a spec file.

        Parameters
        ----------
        model: Model
            Model instance to save to specs file.
        file_name : str
            File to write the model specs to.
        """
        model_dict = model.as_dict()
        # We replace tuples with strings
        for name, items in model_dict.items():
            if not isinstance(items, (list, dict)):
                continue
            item_iterator = items if isinstance(items, list) else items.values()
            for item in item_iterator:
                for prop_name, prop in item.items():
                    if isinstance(prop, dict) and any(isinstance(k, tuple) for k in prop):
                        keys = [f"({k[0]}, {k[1]})" for k in prop]
                        item[prop_name] = {f"{k}": v for k, v in zip(keys, prop.values())}
        _write_dict(file_name, model_dict)

    def save_result_file(self, result: Result, file_name: str):
        """Write a :class:`Result` instance to a spec file.

        Parameters
        ----------
        result : Result
            :class:`Result` instance to write.
        file_name : str | PathLike[str]
            Path to write the result data to.
        """
        result_dict = asdict(result)
        _write_dict(file_name, result_dict)

    def _load_yml(self, file_name: str) -> dict:
        if self.format == "yml_str":
            spec = yaml.safe_load(file_name)
        else:
            with open(file_name) as f:
                spec = yaml.safe_load(f)
        return spec


def _write_dict(file_name: str, d: dict):
    with open(file_name, "w") as f:
        f.write(yaml.dump(d))
