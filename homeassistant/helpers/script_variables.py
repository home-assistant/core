"""Script variables."""
from __future__ import annotations

from typing import Any, Mapping

from homeassistant.core import HomeAssistant, callback

from . import template


class ScriptVariables:
    """Class to hold and render script variables."""

    def __init__(self, variables: dict[str, Any]):
        """Initialize script variables."""
        self.variables = variables
        self._has_template: bool | None = None

    @callback
    def async_render(
        self,
        hass: HomeAssistant,
        run_variables: Mapping[str, Any] | None,
        *,
        render_as_defaults: bool = True,
        limited: bool = False,
    ) -> dict[str, Any]:
        """Render script variables.

        The run variables are used to compute the static variables.

        If `render_as_defaults` is True, the run variables will not be overridden.

        """
        if self._has_template is None:
            self._has_template = template.is_complex(self.variables)
            template.attach(hass, self.variables)

        if not self._has_template:
            if render_as_defaults:
                rendered_variables = dict(self.variables)

                if run_variables is not None:
                    rendered_variables.update(run_variables)
            else:
                rendered_variables = (
                    {} if run_variables is None else dict(run_variables)
                )
                rendered_variables.update(self.variables)

            return rendered_variables

        rendered_variables = {} if run_variables is None else dict(run_variables)

        for key, value in self.variables.items():
            # We can skip if we're going to override this key with
            # run variables anyway
            if render_as_defaults and key in rendered_variables:
                continue

            rendered_variables[key] = template.render_complex(
                value, rendered_variables, limited
            )

        return rendered_variables

    def as_dict(self) -> dict:
        """Return dict version of this class."""
        return self.variables
