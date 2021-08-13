from __future__ import annotations

from dataclasses import dataclass
from os import getcwd
from os import mkdir
from pathlib import Path
from typing import Any
from typing import Literal

from yaml import dump
from yaml import load

from glotaran import __version__ as gta_version
from glotaran.io import load_model
from glotaran.io import load_parameters
from glotaran.model import Model
from glotaran.model import ModelError
from glotaran.parameter import ParameterGroup
from glotaran.parameter.parameter import Keys
from glotaran.project.generators.generator import generators

TEMPLATE = """version: {gta_version}

name: {name}
"""

PROJECT_FILE_NAME = "project.gta"


@dataclass
class Project:
    """A project represents a projectfolder on disk which contains a project file.

    A projectfile is a file in `yml` format with name `project.gta`

    """

    file: str | Path
    name: str
    version: str

    folder: str | Path = None

    def __post_init__(self):
        if isinstance(self.file, str):
            self.file = Path(self.file)
        if self.folder is None:
            self.folder = self.file.parent
        if isinstance(self.folder, str):
            self.folder = Path(self.folder)
        pass

    @classmethod
    def create(cls, name: str | None = None, project_folder: str | None = None):
        if project_folder is None:
            project_folder = getcwd()
        project_folder = Path(project_folder)
        name = name if name else project_folder.name
        project_file = project_folder / PROJECT_FILE_NAME
        with open(project_file, "w") as f:
            f.write(TEMPLATE.format(gta_version=gta_version, name=name))

        with open(project_file) as f:
            project_dict = load(f)
        project_dict["file"] = project_folder
        return cls(**project_dict)

    @classmethod
    def open(cls, project_folder: str):
        project_file = Path(project_folder)
        if not project_file.match(PROJECT_FILE_NAME):
            project_file = project_file / PROJECT_FILE_NAME
        with open(project_file) as f:
            project_dict = load(f)
        project_dict["file"] = project_file
        return cls(**project_dict)

    @property
    def model_dir(self) -> Path:
        return self.folder / "models/"

    def create_model_dir_if_not_exist(self):
        if not self.model_dir.exists():
            mkdir(self.model_dir)

    @property
    def has_models(self) -> bool:
        return len(self.models) != 0

    @property
    def models(self):
        if not self.model_dir.exists():
            return {}
        return {
            model_file.name: load_model(model_file)
            for model_file in self.model_dir.iterdir()
            if model_file.suffix == ".yml" or model_file.suffix == "yaml"
        }

    def load_model(self, name: str) -> Model:
        model_path = self.model_dir / f"{name}.yml"
        if not model_path.exists():
            raise ValueError(f"Model file for model '{name}' does not exist.")
        return load_model(model_path)

    @property
    def parameters_dir(self) -> Path:
        return self.folder / "parameters/"

    def create_parameters_dir_if_not_exist(self):
        if not self.parameters_dir.exists():
            mkdir(self.parameters_dir)

    @property
    def has_parameters(self) -> bool:
        return len(self.parameters) != 0

    @property
    def parameters(self):
        if not self.parameters_dir.exists():
            return {}
        return {
            parameters_file.name: load_parameters(parameters_file)
            for parameters_file in self.parameters_dir.iterdir()
            if parameters_file.suffix in [".yml", ".yaml", ".csv"]
        }

    def load_parameters(self, name: str) -> Model:

        try:
            parameters_path = next(p for p in self.parameters_dir.iterdir() if name in p.name)
        except StopIteration:
            raise ValueError(f"Parameters file for parameters '{name}' does not exist.")
        return load_parameters(parameters_path)

    def generate_model(
        self, name: str, generator: Literal[generators.keys()], generator_arguments: dict[str, Any]
    ):
        if generator not in generators:
            raise ValueError(
                f"Unknown model generator '{generator}'. "
                f"Known generators are: {list(generators.keys())}"
            )
        self.create_model_dir_if_not_exist()
        model = generators[generator](**generator_arguments)
        with open(self.model_dir / f"{name}.yml", "w") as f:
            f.write(dump(model))

    def generate_parameters(
        self,
        model_name: str,
        name: str | None = None,
        fmt: Literal[["yml", "yaml", "csv"]] = "csv",
    ):
        self.create_parameters_dir_if_not_exist()
        model = self.load_model(model_name)
        parameters = {}
        for parameter in model.get_parameters():
            groups = parameter.split(".")
            label = groups.pop()
            if len(groups) == 0:
                if isinstance(parameters, dict) and len(parameters) != 0:
                    raise ModelError(
                        "The root parameter group cannot contain both groups and parameters."
                    )
                elif isinstance(parameters, dict):
                    parameters = []
                    parameters.append(
                        [
                            label,
                            0.0,
                            {
                                Keys.EXPR: "None",
                                Keys.MAX: "None",
                                Keys.MIN: "None",
                                Keys.NON_NEG: "false",
                                Keys.VARY: "true",
                            },
                        ]
                    )
            else:
                if isinstance(parameters, list):
                    raise ModelError(
                        "The root parameter group cannot contain both groups and parameters."
                    )
                this_group = groups.pop()
                group = parameters
                for name in groups:
                    if name not in group:
                        group[name] = {}
                    group = group[name]
                if this_group not in group:
                    group[this_group] = []
                group[this_group].append(
                    [
                        label,
                        0.0,
                        {
                            Keys.EXPR: None,
                            Keys.MAX: "inf",
                            Keys.MIN: "-inf",
                            Keys.NON_NEG: "false",
                            Keys.VARY: "true",
                        },
                    ]
                )

        name = name if name is not None else model_name + "_parameters"
        parameter_file = self.parameters_dir / f"{name}.{fmt}"
        if fmt in ["yml", "yaml"]:
            parameter_yml = dump(parameters)
            with open(parameter_file, "w") as f:
                f.write(parameter_yml)
        elif fmt == "csv":
            parameter_group = ParameterGroup.from_dict(parameters)
            parameter_group.to_csv(parameter_file)

    def run(self):
        if not self.models:
            raise ValueError(f"No models defined for project {self.name}")
