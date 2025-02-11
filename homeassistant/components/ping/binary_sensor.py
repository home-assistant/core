"""Tracks the latency of a host by sending ICMP echo requests (ping)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_IMPORTED_BY
from .coordinator import PingConfigEntry, PingUpdateCoordinator
from .entity import PingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Ping config entry."""
    async_add_entities([PingBinarySensor(entry, entry.runtime_data)])


class PingBinarySensor(PingEntity, BinarySensorEntity):
    """Representation of a Ping Binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_available = False
    _attr_name = None

    def __init__(
        self, config_entry: PingConfigEntry, coordinator: PingUpdateCoordinator
    ) -> None:
        """Initialize the Ping Binary sensor."""
        super().__init__(config_entry, coordinator, config_entry.entry_id)

        # if this was imported just enable it when it was enabled before
        if CONF_IMPORTED_BY in config_entry.data:
            self._attr_entity_registry_enabled_default = bool(
                config_entry.data[CONF_IMPORTED_BY] == "binary_sensor"
            )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.is_alive
