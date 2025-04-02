"""Template entity base class."""

from collections.abc import Sequence
from typing import Any

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.script import Script, _VarsType
from homeassistant.helpers.template import TemplateStateFromEntityId


class AbstractTemplateEntity(Entity):
    """Actions linked to a template entity."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the entity."""

        self.hass = hass
        self._action_scripts: dict[str, Script] = {}

    @property
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        raise NotImplementedError

    @callback
    def _render_script_variables(self) -> dict:
        """Render configured variables."""
        raise NotImplementedError

    def add_script(
        self,
        script_id: str,
        config: Sequence[dict[str, Any]],
        name: str,
        domain: str,
    ):
        """Add an action script."""

        self._action_scripts[script_id] = Script(
            self.hass,
            config,
            f"{name} {script_id}",
            domain,
        )

    async def async_run_script(
        self,
        script: Script,
        *,
        run_variables: _VarsType | None = None,
        context: Context | None = None,
    ) -> None:
        """Run an action script."""
        if run_variables is None:
            run_variables = {}
        await script.async_run(
            run_variables={
                "this": TemplateStateFromEntityId(self.hass, self.entity_id),
                **self._render_script_variables(),
                **run_variables,
            },
            context=context,
        )
