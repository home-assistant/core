"""Trigger sensor entities."""
import logging

from homeassistant.components.trigger import TriggerUpdateCoordinator
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import template, update_coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up trigger entities."""
    if discovery_info is None:
        raise HomeAssistantError("Platform setup not supported")

    async_add_entities(
        TriggerSensorEntity(discovery_info["coordinator"], object_id, config)
        for object_id, config in discovery_info["entities"].items()
    )


class TriggerSensorEntity(update_coordinator.CoordinatorEntity):
    def __init__(
        self, coordinator: TriggerUpdateCoordinator, object_id: str, config: dict
    ):
        super().__init__(coordinator)
        self._object_id = object_id
        if object_id and coordinator.unique_id:
            self._unique_id = f"{coordinator.unique_id}-{object_id}"
        else:
            self._unique_id = None
        self._config = config
        self._state = None
        self._available = True

    @property
    def name(self):
        return self._config.get("name") or self._object_id

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        return self._state

    async def async_added_to_hass(self) -> None:
        self._config["value_template"].hass = self.hass
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_set_context(self.coordinator.data["context"])
        try:
            self._state = self._config["value_template"].async_render(
                self.coordinator.data["run_variables"]
            )
            self._available = True
        except template.TemplateError as err:
            _LOGGER.error("Error rendering template: %s", err)
            self._available = False

        self.async_write_ha_state()
