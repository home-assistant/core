"""Script variables."""

from collections import ChainMap, UserDict
from collections.abc import KeysView, Mapping
from dataclasses import dataclass, field
from typing import Any, cast, override

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import json_loads

from . import template
from .json import json_dumps


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


class StoredVariables:
    """Class to hold variables which are stored across script runs.

    A single instance is shared by all runs of a script. The stored values
    are read live by every run, so `values` must only be mutated in place.
    """

    def __init__(self, defaults: ScriptVariables) -> None:
        """Initialize stored variables with their default values."""
        self.defaults = defaults
        self.values: dict[str, Any] = {}

    @property
    def names(self) -> KeysView[str]:
        """Return the names of the stored variables."""
        return self.defaults.variables.keys()

    @callback
    def async_render(
        self, hass: HomeAssistant, run_variables: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        """Return the run variables with the stored values on top.

        Run variables with the name of a stored variable are discarded.
        Defaults of stored variables without a value are rendered and stored.
        """
        variables = {
            key: value
            for key, value in (run_variables or {}).items()
            if key not in self.names
        }
        if missing := [name for name in self.names if name not in self.values]:
            rendered = self.defaults.async_render(hass, {**variables, **self.values})
            for name in missing:
                self.assign(name, rendered[name])
        return {**variables, **self.values}

    def assign(self, key: str, value: Any) -> None:
        """Store a value, normalized to JSON compatible types."""
        try:
            self.values[key] = json_loads(json_dumps(value))
        except (TypeError, ValueError) as err:
            raise HomeAssistantError(
                f"Stored variable '{key}' must be JSON serializable: {err}"
            ) from err

    def restore(self, values: Mapping[str, Any]) -> None:
        """Restore previously stored values, dropping unknown variables."""
        self.values.clear()
        self.values.update(
            {key: value for key, value in values.items() if key in self.names}
        )


@dataclass
class _ParallelData:
    """Data used in each parallel sequence."""

    # `protected` is for variables that need special protection
    # in parallel sequences. What this means is that such a
    # variable defined in one parallel sequence will not be
    # clobbered by the variable with the same name assigned in
    # another parallel sequence. It also means that such a
    # variable will not be visible in the outer scope.
    # Currently the only such variable is `wait`.
    protected: dict[str, Any] = field(default_factory=dict)
    # `outer_scope_writes` is for variables that are written
    # to the outer scope from a parallel sequence. This is used
    # for generating correct traces of changed variables for
    # each of the parallel sequences, isolating them from one
    # another.
    outer_scope_writes: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class ScriptRunVariables(UserDict[str, Any]):
    """Class to hold script run variables.

    The purpose of this class is to provide proper variable
    scoping semantics for scripts. Each instance institutes a
    new local scope, in which variables can be defined. Each
    instance has a reference to the previous instance, except
    for the top-level instance. The instances therefore form a
    chain, in which variable lookup and assignment is performed.
    The variables defined lower in the chain naturally override
    those defined higher up.
    """

    # _previous is the previous ScriptRunVariables in the chain
    _previous: ScriptRunVariables | None = None
    # _parent is the previous non-empty ScriptRunVariables in the chain
    _parent: ScriptRunVariables | None = None

    # _local_data is the store for local variables
    _local_data: dict[str, Any] | None = None
    # _parallel_data is used for each parallel sequence
    _parallel_data: _ParallelData | None = None
    # _stored_variables is only set on the top-level instance; the stored
    # values form the bottom layer of the scope chain and are read live
    _stored_variables: StoredVariables | None = None

    # _non_parallel_scope includes all scopes all the way to
    # the most recent parallel split
    _non_parallel_scope: ChainMap[str, Any]
    # _full_scope includes all scopes (all the way to the top-level)
    _full_scope: ChainMap[str, Any]

    @classmethod
    def create_top_level(
        cls,
        initial_data: Mapping[str, Any] | None = None,
        *,
        stored_variables: StoredVariables | None = None,
    ) -> ScriptRunVariables:
        """Create a new top-level ScriptRunVariables.

        :param stored_variables: Variables stored across runs. Their values
            are read live and assignments to them are stored immediately.
            Initial data with the name of a stored variable is ignored.
        """
        local_data: dict[str, Any] = {}
        if stored_variables is None:
            non_parallel_scope = full_scope = ChainMap(local_data)
        else:
            non_parallel_scope = full_scope = ChainMap(
                local_data, stored_variables.values
            )
        self = cls(
            _local_data=local_data,
            _non_parallel_scope=non_parallel_scope,
            _full_scope=full_scope,
            _stored_variables=stored_variables,
        )
        if initial_data is not None:
            stored_names = stored_variables.names if stored_variables else ()
            self.update(
                {
                    key: value
                    for key, value in initial_data.items()
                    if key not in stored_names
                }
            )
        return self

    def enter_scope(self, *, parallel: bool = False) -> ScriptRunVariables:
        """Return a new child scope.

        :param parallel: Whether the new scope starts a parallel sequence.
        """
        if self._local_data is not None or self._parallel_data is not None:
            parent = self
        else:
            parent = cast(  # top level always has local data, so we can cast safely
                ScriptRunVariables, self._parent
            )

        parallel_data: _ParallelData | None
        if not parallel:
            parallel_data = None
            non_parallel_scope = self._non_parallel_scope
            full_scope = self._full_scope
        else:
            parallel_data = _ParallelData()
            non_parallel_scope = ChainMap(
                parallel_data.protected, parallel_data.outer_scope_writes
            )
            full_scope = self._full_scope.new_child(parallel_data.protected)

        return ScriptRunVariables(
            _previous=self,
            _parent=parent,
            _parallel_data=parallel_data,
            _non_parallel_scope=non_parallel_scope,
            _full_scope=full_scope,
        )

    def exit_scope(self) -> ScriptRunVariables:
        """Exit the current scope.

        Does no clean-up, but simply returns the previous scope.
        """
        if self._previous is None:
            raise ValueError("Cannot exit top-level scope")
        return self._previous

    @override
    def __delitem__(self, key: str) -> None:
        """Delete a variable (disallowed)."""
        raise TypeError("Deleting items is not allowed in ScriptRunVariables.")

    @override
    def __setitem__(self, key: str, value: Any) -> None:
        """Assign value to a variable."""
        self._assign(key, value, parallel_protected=False)

    def assign_parallel_protected(self, key: str, value: Any) -> None:
        """Assign value to a variable which is to be protected in parallel sequences."""
        self._assign(key, value, parallel_protected=True)

    def _assign(self, key: str, value: Any, *, parallel_protected: bool) -> None:
        """Assign value to a variable.

        Value is always assigned to the variable in the nearest
        scope, in which it is defined. If the variable is not
        defined at all, it is created in the top-level scope.
        Assignments to stored variables are stored immediately.

        :param parallel_protected: Whether variable is to be
            protected in parallel sequences.
        """
        if self._local_data is not None and key in self._local_data:
            self._local_data[key] = value
            return

        if self._parent is None:
            if (
                self._stored_variables is not None
                and key in self._stored_variables.names
            ):
                self._stored_variables.assign(key, value)
                return
            assert self._local_data is not None  # top level always has local data
            self._local_data[key] = value
            return

        if self._parallel_data is not None:
            if parallel_protected:
                self._parallel_data.protected[key] = value
                return
            self._parallel_data.protected.pop(key, None)
            self._parallel_data.outer_scope_writes[key] = value

        self._parent._assign(key, value, parallel_protected=parallel_protected)  # noqa: SLF001

    def define_local(self, key: str, value: Any) -> None:
        """Define a local variable and assign value to it."""
        if self._local_data is None:
            self._local_data = {}
            self._non_parallel_scope = self._non_parallel_scope.new_child(
                self._local_data
            )
            self._full_scope = self._full_scope.new_child(self._local_data)
        self._local_data[key] = value

    @property
    @override
    def data(self) -> Mapping[str, Any]:  # type: ignore[override]
        """Return variables in full scope.

        Defined here for UserDict compatibility.
        """
        return self._full_scope

    @property
    def non_parallel_scope(self) -> Mapping[str, Any]:
        """Return variables in non-parallel scope."""
        return self._non_parallel_scope

    @property
    def local_scope(self) -> Mapping[str, Any]:
        """Return variables in local scope."""
        return self._local_data if self._local_data is not None else {}
