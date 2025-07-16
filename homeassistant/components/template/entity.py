"""Template entity base class."""

from abc import abstractmethod
from collections.abc import Sequence
from typing import Any

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.script import Script, _VarsType
from homeassistant.helpers.template import TemplateStateFromEntityId
from homeassistant.helpers.typing import ConfigType

from .const import CONF_OBJECT_ID


class AbstractTemplateEntity(Entity):
    """Actions linked to a template entity."""

    _entity_id_format: str

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize the entity."""

        self.hass = hass
        self._action_scripts: dict[str, Script] = {}

        if (object_id := config.get(CONF_OBJECT_ID)) is not None:
            self.entity_id = async_generate_entity_id(
                self._entity_id_format, object_id, hass=self.hass
            )

        device_registry = dr.async_get(hass)
        if (device_id := config.get(CONF_DEVICE_ID)) is not None:
            self.device_entry = device_registry.async_get(device_id)

    @property
    @abstractmethod
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""

    @callback
    @abstractmethod
    def _render_script_variables(self) -> dict:
        """Render configured variables."""

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
