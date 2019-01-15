"""This package contains glotarans base model."""


import typing
import numpy as np
import xarray as xr

from glotaran.analysis.fitresult import FitResult
from glotaran.analysis.simulation import simulate

from .parameter_group import ParameterGroup


class BaseModel:
    """Base Model contains basic functions for model.

    The basemodel already has the compartment attribute, which all model
    implementations will need.
    """

    @classmethod
    def from_dict(cls, model_dict: typing.Dict):
        """Creates a model from a dictionary.

        Parameters
        ----------
        model_dict : dict
            Dictionary containing the model.

        Returns
        -------
        model : The parsed model.
        """

        model = cls()

        # iterate over items
        for name, attribute in list(model_dict.items()):

            # we determine if we the item is known by the model by looking for
            # a setter with same name.

            if hasattr(model, f'set_{name}'):

                # get the set function
                set = getattr(model, f'set_{name}')

                # we retrieve the actual class from the signature
                for label, item in attribute.items():
                    item_cls = set.__func__.__annotations__['item']
                    is_typed = hasattr(item_cls, "_glotaran_model_item_typed")
                    if isinstance(item, dict):
                        if is_typed:
                            if 'type' not in item:
                                raise Exception(f"Missing type for attribute '{name}'")
                            item_type = item['type']

                            if item_type not in item_cls._glotaran_model_item_types:
                                raise Exception(f"Unknown type '{item_type}' "
                                                f"for attribute '{name}'")
                            item_cls = \
                                item_cls._glotaran_model_item_types[item_type]
                        item['label'] = label
                        set(label, item_cls.from_dict(item))
                    elif isinstance(item, list):
                        if is_typed:
                            if len(item) < 2 and len(item) is not 1:
                                raise Exception(f"Missing type for attribute '{name}'")
                            item_type = item[1] if len(item) is not 1 and \
                                hasattr(item_cls, 'label') else item[0]

                            if item_type not in item_cls._glotaran_model_item_types:
                                raise Exception(f"Unknown type '{item_type}' "
                                                f"for attribute '{name}'")
                            item_cls = \
                                item_cls._glotaran_model_item_types[item_type]
                        item = [label] + item
                        set(label, item_cls.from_list(item))
                del model_dict[name]

            elif hasattr(model, f'add_{name}'):

                # get the set function
                add = getattr(model, f'add_{name}')

                # we retrieve the actual class from the signature
                for item in attribute:
                    item_cls = add.__func__.__annotations__['item']
                    is_typed = hasattr(item_cls, "_glotaran_model_item_typed")
                    if isinstance(item, dict):
                        if is_typed:
                            if 'type' not in item:
                                raise Exception(f"Missing type for attribute '{name}'")
                            item_type = item['type']

                            if item_type not in item_cls._glotaran_model_item_types:
                                raise Exception(f"Unknown type '{item_type}' "
                                                f"for attribute '{name}'")
                            item_cls = \
                                item_cls._glotaran_model_item_types[item_type]
                        add(item_cls.from_dict(item))
                    elif isinstance(item, list):
                        if is_typed:
                            if len(item) < 2 and len(item) is not 1:
                                raise Exception(f"Missing type for attribute '{name}'")
                            item_type = item[1] if len(item) is not 1 and \
                                hasattr(item_cls, 'label') else item[0]

                            if item_type not in item_cls._glotaran_model_item_types:
                                raise Exception(f"Unknown type '{item_type}' "
                                                f"for attribute '{name}'")
                            item_cls = \
                                item_cls._glotaran_model_item_types[item_type]
                        add(item_cls.from_list(item))
                del model_dict[name]

        return model

    def simulate(self,
                 dataset: str,
                 parameter: ParameterGroup,
                 axis: typing.Dict[str, np.ndarray],
                 noise: bool = False,
                 noise_std_dev: float = 1.0,
                 noise_seed: int = None,
                 ) -> xr.DataArray:
        """Simulates the model.

        Parameters
        ----------
        dataset : str
            Label of the dataset to simulate
        parameter : glotaran.model.ParameterGroup
            The parameters for the simulation.
        axis : Dict[str, np.ndarray]
            A dictory with axis
        noise : bool, optional
            (Default = False)
            If `True` noise is added to the simulated data.
        noise_std_dev : float
            (Default value = 1.0)
            the standart deviation of the noise.
        noise_seed : int, optional
            Seed for the noise.

        Returns
        -------
        data: xr.DataArray
        """
        return simulate(self, parameter, dataset, axis, noise=noise,
                        noise_std_dev=noise_std_dev, noise_seed=noise_seed)

    def fit(self,
            parameter: ParameterGroup,
            data: typing.Dict[str, typing.Union[xr.Dataset, xr.DataArray]],
            nnls: bool = False,
            verbose: bool = True,
            max_nfev: int = None,
            group_atol: int = 0,
            ) -> FitResult:
        """Performs a fit of the model.

        Parameters
        ----------
        data : dict(str, union(xr.Dataset, xr.DataArray))
            A dictonary containing all datasets with their labels as keys.
        parameter : glotaran.model.ParameterGroup
            The parameter,
        nnls : bool, optional
            (default = False)
            If `True` non-linear least squaes optimizing is used instead of variable projection.
        verbose : bool, optional
            (default = True)
            If `True` feedback is printed at every iteration.
        max_nfev : int, optional
            (default = None)
            Maximum number of function evaluations. `None` for unlimited.
        group_atol : float, optional
            (default = 0)
            The tolerance for grouping datasets along the estimated axis.

        Returns
        -------
        result: glotaran.analysis.fitresult.FitResult 
            The result of the fit.
        """
        result = FitResult(self, data, parameter, nnls, atol=group_atol)
        result.optimize(verbose=verbose, max_nfev=max_nfev)
        return result

    def errors(self) -> typing.List[str]:
        """Returns a list of errors in the model.

        Returns
        -------
        errors : list(str)
        """
        attrs = getattr(self, '_glotaran_model_attributes')

        errors = []

        for attr in attrs:
            attr = getattr(self, attr)
            if isinstance(attr, list):
                for item in attr:
                    item.validate_model(self, errors=errors)
            else:
                for _, item in attr.items():
                    item.validate_model(self, errors=errors)

        return errors

    def valid(self) -> bool:
        """valid checks the model for errors.

        Returns
        -------
        valid : bool
            False if at least one error in the model, else True.
        """
        return len(self.errors()) is 0

    def errors_parameter(self, parameter: ParameterGroup) -> typing.List[str]:
        """Returns a list of missing parameters.

        Parameters
        ----------
        parameter : glotaran.model.ParameterGroup

        Returns
        -------
        errors : list(str)
        """
        attrs = getattr(self, '_glotaran_model_attributes')

        errors = []

        for attr in attrs:
            attr = getattr(self, attr)
            if isinstance(attr, list):
                for item in attr:
                    item.validate_model(self, errors=errors)
            else:
                for _, item in attr.items():
                    item.validate_model(self, errors=errors)

        return errors

    def valid_parameter(self, parameter: ParameterGroup) -> bool:
        """valid checks the parameter for errors.

        Parameters
        ----------
        parameter : glotaran.model.ParameterGroup

        Returns
        -------
        valid : bool
            False if at least one error in the parameter, else True.
        """
        return len(self.errors_parameter(parameter)) is 0

    def __str__(self):
        attrs = getattr(self, '_glotaran_model_attributes')
        string = "# Model\n\n"
        string += f"_Type_: {self.model_type}\n\n"

        for attr in attrs:
            string += f"## {attr}\n"

            for label, item in getattr(self, attr).items():
                string += f'{item}\n'
        return string
