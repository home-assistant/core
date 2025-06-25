"""Template entity base class."""

from collections.abc import Sequence
from typing import Any

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.script import Script, _VarsType
from homeassistant.helpers.template import TemplateStateFromEntityId
from homeassistant.helpers.typing import ConfigType

from .const import CONF_OBJECT_ID


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

    def initialize(self, config: ConfigType, entity_id_format: str) -> None:
        """Initialize entity information."""
        if (object_id := config.get(CONF_OBJECT_ID)) is not None:
            self.entity_id = async_generate_entity_id(
                entity_id_format, object_id, hass=self.hass
            )

        self._attr_device_info = async_device_info_to_link_from_device_id(
            self.hass,
            config.get(CONF_DEVICE_ID),
        )

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
