from __future__ import annotations

from dataclasses import dataclass
from os import getcwd
from os import mkdir
from pathlib import Path
from typing import Literal

from yaml import dump
from yaml import load

from glotaran import __version__ as gta_version
from glotaran.io import load_model
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

    def models(self):
        if not self.model_dir.exists():
            return {}
        #  print(model_file)
        return {
            model_file.name: load_model(model_file)
            for model_file in self.model_dir.iterdir()
            if "yml" in model_file
        }

    def has_models(self):
        return len(self.models()) != 0

    def create_model(self, model_type: Literal[generators.keys()] = "decay_parallel"):
        self.create_model_dir_if_not_exist()
        model = generators[model_type]
        with open(self.model_dir / "p_model.yml", "w") as f:
            f.write(dump(model()))

    def run(self):
        if not self.models:
            raise ValueError(f"No models defined for project {self.name}")