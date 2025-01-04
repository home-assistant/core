"""Script variables."""

from __future__ import annotations

from collections import UserDict
from collections.abc import Mapping
from typing import Any

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


class ScriptRunVariables(UserDict[str, Any]):
    """Class to hold script run variables."""

    _parent: ScriptRunVariables
    _local_variables: set[str] | None

    def __init__(
        self,
        initial: Mapping[str, Any] | None = None,
        parent: ScriptRunVariables | None = None,
        parallel: bool = False,
    ) -> None:
        """Initialize script run variables."""
        super().__init__()

        if parent is not None:
            self._parent = parent
            self.data = parent.data
            self._local_variables = None

            if parallel:
                self.data = self.data.copy()
                self._local_variables = set()
        else:
            self._parent = self
            self._local_variables = set()

        if initial is not None:
            self.update(initial)

    def __delitem__(self, key: str) -> None:
        """Delete a variable."""
        raise TypeError("Deleting items is not allowed in ScriptRunVariables.")

    def __setitem__(self, key: str, value: Any) -> None:
        """Assign value to a variable."""
        if self._local_variables is None:
            self._parent[key] = value
            return

        self.data[key] = value

        if key in self._local_variables or self._parent is self:
            self._local_variables.add(key)
        else:
            self._parent[key] = value

    def assign(self, new_vars: ScriptVariables) -> None:
        """Assign values to variables."""
        for key, value in new_vars.async_simple_render(self.data).items():
            self[key] = value

    def define(self, new_vars: ScriptVariables) -> None:
        """Define local variables."""
        self._ensure_local()
        assert self._local_variables is not None
        for key, value in new_vars.async_simple_render(self.data).items():
            self.data[key] = value
            self._local_variables.add(key)

    def define_single(self, key: str, value: Any) -> None:
        """Define a local variable."""
        self._ensure_local()
        assert self._local_variables is not None
        self.data[key] = value
        self._local_variables.add(key)

    def _ensure_local(self) -> None:
        if self._local_variables is None:
            self.data = self.data.copy()
            self._local_variables = set()

    def enter_scope(self, parallel: bool = False) -> ScriptRunVariables:
        """Enter a new scope."""
        return ScriptRunVariables(parent=self, parallel=parallel)

    def exit_scope(self) -> ScriptRunVariables:
        """Exit the current scope."""
        return self._parent
