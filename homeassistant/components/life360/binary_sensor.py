"""Support for Life360 binary sensor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

ATTR_REASON = "reason"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the binary sensor platform."""
    coordinator = hass.data[DOMAIN].coordinators[entry.entry_id]
    name = f"Life360 Online ({entry.data[CONF_USERNAME]})"
    async_add_entities([Life360BinarySensor(coordinator, name)])


class Life360BinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Life360 Binary Sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, name: str) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._attr_unique_id = cast(ConfigEntry, coordinator.config_entry).entry_id
        self._attr_name = name
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_is_on = self.online

    @property
    def online(self) -> bool:
        """Return if online."""
        return super().available

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.online
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        attrs = {}
        if not self.online:
            if isinstance(self.coordinator.last_exception, ConfigEntryAuthFailed):
                attrs[ATTR_REASON] = "Authorization failure"
            elif isinstance(self.coordinator.last_exception, UpdateFailed):
                attrs[ATTR_REASON] = "Server communication failure"
        return attrs
