import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import RedgtechDataUpdateCoordinator
from typing import List

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry_data.coordinator

    entities = []
    if coordinator.data:
        existing_entities = hass.data.get(DOMAIN, {}).get("entities", [])
        for item in coordinator.data:
            entity_id = item["id"]
            if entity_id not in existing_entities:
                if item["type"] == "switch":
                    entities.append(RedgtechSwitch(coordinator, item))
                    existing_entities.append(entity_id)

        hass.data.setdefault(DOMAIN, {})["entities"] = existing_entities

    async_add_entities(entities)

class RedgtechSwitch(CoordinatorEntity[RedgtechDataUpdateCoordinator], SwitchEntity):
    """Representation of a Redgtech switch."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RedgtechDataUpdateCoordinator, data: dict):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.api = coordinator.api
        self._state = data["state"] == "on"
        self._name = data["name"]
        self._endpoint_id = data["id"]
        self._attr_unique_id = f"redgtech_{self._endpoint_id}"

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        """Send the state to the API and update immediately."""
        _LOGGER.debug("Setting state of %s to %s", self._name, state)

        success = await self.api.set_switch_state(self._endpoint_id, state)
        if success:
            self._state = state
            self.async_write_ha_state()
            _LOGGER.debug("State of %s set to %s", self._name, state)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set state for %s", self._name)
