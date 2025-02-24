"""Script variables."""

from __future__ import annotations

from collections import ChainMap, UserDict
from collections.abc import Mapping
from dataclasses import dataclass, field
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

        The run variables are included in the result.
        The run variables are used to compute the rendered variable values.
        The run variables will not be overridden.
        The rendering happens one at a time, with previous results influencing the next.
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
        """Render script variables.

        Simply renders the variables, the run variables are not included in the result.
        The run variables are used to compute the rendered variable values.
        The rendering happens one at a time, with previous results influencing the next.
        """
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


@dataclass
class _ParallelStore:
    """Store used in each parallel sequence."""

    # `special` is for variables that need special treatment in parallel sequences.
    # Currently the only such variable is `wait`.
    special: dict[str, Any] = field(default_factory=dict)
    # `outer_scope_writes` is for variables that are written to the outer scope from
    # a parallel sequence. This is used for generating correct traces of changed variables
    # for each of the parallel sequences, isolating them from one another.
    outer_scope_writes: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class ScriptRunVariables(UserDict[str, Any]):
    """Class to hold script run variables.

    It is a subclass of UserDict, so it has all the usual additional methods available.
    Operations using those methods are equivalent to assigning values to variables.
    """

    # _previous is the previous ScriptRunVariables in the chain
    _previous: ScriptRunVariables | None = None
    # _parent is the previous non-empty ScriptRunVariables in the chain
    _parent: ScriptRunVariables | None = None

    # _local_store is the store for local variables
    _local_store: dict[str, Any] | None = None
    # _parallel store is used for each parallel sequence
    _parallel_store: _ParallelStore | None = None

    # _non_parallel_scope includes all scopes all the way to the most recent parallel split
    _non_parallel_scope: ChainMap[str, Any]
    # _full_scope includes all scopes (all the way to the top-level)
    _full_scope: ChainMap[str, Any]

    @classmethod
    def create_top_level(
        cls,
        initial_data: Mapping[str, Any] | None = None,
    ) -> ScriptRunVariables:
        """Create a new top-level ScriptRunVariables."""
        local_store: dict[str, Any] = {}
        non_parallel_scope = full_scope = ChainMap(local_store)
        self = cls(
            _local_store=local_store,
            _non_parallel_scope=non_parallel_scope,
            _full_scope=full_scope,
        )
        if initial_data is not None:
            self.update(initial_data)
        return self

    def enter_scope(self, *, parallel: bool = False) -> ScriptRunVariables:
        """Return a new child scope.

        :param parallel: Whether the new scope starts a parallel sequence.
        """
        if self._local_store is not None or self._parallel_store is not None:
            parent = self
        else:
            parent = cast(  # top level always has a local store, so we can cast safely
                ScriptRunVariables, self._parent
            )

        parallel_store: _ParallelStore | None
        if not parallel:
            parallel_store = None
            non_parallel_scope = self._non_parallel_scope
            full_scope = self._full_scope
        else:
            parallel_store = _ParallelStore()
            non_parallel_scope = ChainMap(parallel_store.outer_scope_writes)
            full_scope = self._full_scope.new_child(parallel_store.special)

        return ScriptRunVariables(
            _previous=self,
            _parent=parent,
            _parallel_store=parallel_store,
            _non_parallel_scope=non_parallel_scope,
            _full_scope=full_scope,
        )

    def exit_scope(self) -> ScriptRunVariables:
        """Exit the current scope.

        Does no clean-up, but simply returns the previous scope.
        """
        if self._previous is None:
            raise ValueError("Cannot exit root scope")
        return self._previous

    def __setitem__(self, key: str, value: Any) -> None:
        """Assign value to a variable. Equivalent to `assign_single`."""
        self.assign_single(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete a variable (disallowed)."""
        raise TypeError("Deleting items is not allowed in ScriptRunVariables.")

    def assign_single(
        self, key: str, value: Any, *, parallel_special: bool = False
    ) -> None:
        """Assign value to a variable.

        Value is always assigned to the variable in the nearest scope, in which it is defined.
        If the variable is not defined at all, it is created in the top-level scope.

        :param parallel_special: Whether variable is to be treated specially in parallel sequences.
        """
        if self._local_store is not None and key in self._local_store:
            self._local_store[key] = value
            return

        if self._parent is None:
            assert self._local_store is not None  # top level always has a local store
            self._local_store[key] = value
            return

        if self._parallel_store is not None:
            self._parallel_store.outer_scope_writes[key] = value
            if parallel_special:
                self._parallel_store.special[key] = value
            else:
                self._parallel_store.special.pop(key, None)

        self._parent.assign_single(key, value, parallel_special=parallel_special)

    def assign(self, new_vars: ScriptVariables) -> None:
        """Assign rendered values to variables.

        First renders the variable values in order and then assigns each of them.
        Value is always assigned to the variable in the nearest scope, in which it is defined.
        If the variable is not defined at all, it is created in the top-level scope.
        """
        for key, value in new_vars.async_simple_render(self).items():
            self.assign_single(key, value)

    def define_single(self, key: str, value: Any) -> None:
        """Define a local variable and assign value to it."""
        self._ensure_local()
        assert self._local_store is not None
        self._local_store[key] = value

    def define(self, new_vars: ScriptVariables) -> None:
        """Define local variables and assign rendered values to them.

        First renders the variable values in order and then assigns each of them.
        """
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
    def full_scope(self) -> Mapping[str, Any]:
        """Return variables in full scope."""
        return self._full_scope

    @property
    def non_parallel_scope(self) -> Mapping[str, Any]:
        """Return variables in non-parallel scope."""
        return self._non_parallel_scope

    @property
    def local_scope(self) -> Mapping[str, Any]:
        """Return variables in local scope."""
        return self._local_store if self._local_store is not None else {}
