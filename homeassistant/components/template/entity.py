"""Template entity base class."""

from typing import Any, cast

from homeassistant.components.blueprint import CONF_USE_BLUEPRINT
from homeassistant.const import CONF_PATH, CONF_VARIABLES
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.script import Script, _VarsType
from homeassistant.helpers.template import TemplateStateFromEntityId
from homeassistant.helpers.typing import ConfigType


class AbstractTemplateEntity(Entity):
    """Actions linked to a template entity."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize the entity."""

        self._action_scripts: dict[str, Script] = {}

        if config is not None:
            self._run_variables = config.get(CONF_VARIABLES, {})
            self._blueprint_inputs: dict | None = config.get("raw_blueprint_inputs")
        else:
            self._run_variables = {}
            self._blueprint_inputs = None

    @property
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""
        if self._blueprint_inputs is None:
            return None
        return cast(str, self._blueprint_inputs[CONF_USE_BLUEPRINT][CONF_PATH])

    def add_script(
        self, script_id: str, config: dict[str, Any], name: str, domain: str
    ):
        """Add an action script."""

        self._action_scripts[script_id] = Script(
            self.hass,
            config,
            f"{name} {script_id}",
            domain,
        )

    @callback
    def _render_variables(self) -> dict:
        if isinstance(self._run_variables, dict):
            return self._run_variables

        return self._run_variables.async_render(
            self.hass,
            {
                "this": TemplateStateFromEntityId(self.hass, self.entity_id),
            },
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
                **self._render_variables(),
                **run_variables,
            },
            context=context,
        )
