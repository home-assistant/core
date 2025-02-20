"""Script variables."""

from __future__ import annotations

from collections import ChainMap, UserDict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.core import HomeAssistant, callback

from . import template


class ScriptVariables:
    """Class to hold and render script variables."""

    def __init__(self, variables: dict[str, Any]) -> None:
        """Initialize script variables."""
        self.variables = variables
        self._has_template: bool | None = None

    @callback
    def async_render(
        self,
        hass: HomeAssistant,
        run_variables: Mapping[str, Any] | None,
        *,
        limited: bool = False,
    ) -> dict[str, Any]:
        """Render script variables.

        The run variables are used to compute the static variables.
        The run variables will not be overridden.
        """
        if self._has_template is None:
            self._has_template = template.is_complex(self.variables)

        if not self._has_template:
            rendered_variables = dict(self.variables)

            if run_variables is not None:
                rendered_variables.update(run_variables)

            return rendered_variables

        rendered_variables = {} if run_variables is None else dict(run_variables)

        for key, value in self.variables.items():
            # We can skip if we're going to override this key with
            # run variables anyway
            if key in rendered_variables:
                continue

            rendered_variables[key] = template.render_complex(
                value, rendered_variables, limited
            )

        return rendered_variables

    @callback
    def async_simple_render(self, run_variables: Mapping[str, Any]) -> dict[str, Any]:
        """Render script variables."""
        if self._has_template is None:
            self._has_template = template.is_complex(self.variables)

        if not self._has_template:
            return self.variables

        run_variables = dict(run_variables)
        rendered_variables = {}

        for key, value in self.variables.items():
            rendered_variable = template.render_complex(value, run_variables)
            rendered_variables[key] = rendered_variable
            run_variables[key] = rendered_variable

        return rendered_variables

    def as_dict(self) -> dict[str, Any]:
        """Return dict version of this class."""
        return self.variables


@dataclass(kw_only=True)
class ScriptRunVariables(UserDict[str, Any]):
    """Class to hold script run variables."""

    _previous: ScriptRunVariables | None = None
    _parent: ScriptRunVariables | None = None

    _local_store: dict[str, Any] | None = None
    _parallel_store: tuple[dict[str, Any], dict[str, Any]] | None = None

    _non_parallel_scope: ChainMap[str, Any]
    _full_scope: ChainMap[str, Any]

    @classmethod
    def create_top_level(
        cls,
        initial_data: Mapping[str, Any] | None = None,
    ) -> ScriptRunVariables:
        """Create a new ScriptRunVariables."""
        local_store: dict[str, Any] = {}
        non_parallel_scope = full_scope = ChainMap(local_store)
        variables = cls(
            _local_store=local_store,
            _non_parallel_scope=non_parallel_scope,
            _full_scope=full_scope,
        )
        if initial_data is not None:
            variables.update(initial_data)
        return variables

    def enter_scope(self, parallel: bool = False) -> ScriptRunVariables:
        """Enter a new scope."""
        if self._local_store is not None or self._parallel_store is not None:
            parent = self
        else:
            parent = cast(  # top level always has a local store, so we can cast safely
                ScriptRunVariables, self._parent
            )

        if not parallel:
            parallel_store: tuple[dict[str, Any], dict[str, Any]] | None = None
            non_parallel_scope = self._non_parallel_scope
            full_scope = self._full_scope
        else:
            parallel_store = ({}, {})
            non_parallel_scope = ChainMap(parallel_store[1])
            full_scope = self._full_scope.new_child(parallel_store[0])

        return ScriptRunVariables(
            _previous=self,
            _parent=parent,
            _parallel_store=parallel_store,
            _non_parallel_scope=non_parallel_scope,
            _full_scope=full_scope,
        )

    def exit_scope(self) -> ScriptRunVariables:
        """Exit the current scope."""
        if self._previous is None:
            raise ValueError("Cannot exit root scope")
        return self._previous

    def __setitem__(self, key: str, value: Any) -> None:
        """Assign value to a variable."""
        self.assign_single(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete a variable."""
        raise TypeError("Deleting items is not allowed in ScriptRunVariables.")

    def assign_single(
        self, key: str, value: Any, *, parallel_copy: bool = False
    ) -> None:
        """Assign a value to a variable."""
        if self._local_store is not None and key in self._local_store:
            self._local_store[key] = value
            return

        if self._parent is None:
            assert self._local_store is not None  # top level always has a local store
            self._local_store[key] = value
            return

        if self._parallel_store is not None:
            self._parallel_store[1][key] = value
            if parallel_copy:
                self._parallel_store[0][key] = value
            else:
                self._parallel_store[0].pop(key, None)

        self._parent.assign_single(key, value, parallel_copy=parallel_copy)

    def assign(self, new_vars: ScriptVariables) -> None:
        """Assign values to variables."""
        for key, value in new_vars.async_simple_render(self).items():
            self.assign_single(key, value)

    def define_single(self, key: str, value: Any) -> None:
        """Define a local variable."""
        self._ensure_local()
        assert self._local_store is not None
        self._local_store[key] = value

    def define(self, new_vars: ScriptVariables) -> None:
        """Define local variables."""
        self._ensure_local()
        assert self._local_store is not None
        for key, value in new_vars.async_simple_render(self).items():
            self._local_store[key] = value

    def _ensure_local(self) -> None:
        if self._local_store is None:
            self._local_store = {}
            self._non_parallel_scope = self._non_parallel_scope.new_child(
                self._local_store
            )
            self._full_scope = self._full_scope.new_child(self._local_store)

    @property
    def data(self) -> Mapping[str, Any]:  # type: ignore[override]
        """Return variables in full scope.

        Defined here for UserDict compatibility.
        """
        return self._full_scope

    @property
    def local_scope(self) -> Mapping[str, Any]:
        """Return variables in local scope."""
        return self._local_store if self._local_store is not None else {}

    @property
    def non_parallel_scope(self) -> Mapping[str, Any]:
        """Return variables in non-parallel scope."""
        return self._non_parallel_scope
