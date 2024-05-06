"""Sensors flow for Withings."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er

from .const import DOMAIN
from .coordinator import WithingsBedPresenceDataUpdateCoordinator
from .entity import WithingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id].bed_presence_coordinator

    ent_reg = er.async_get(hass)

    callback: Callable[[], None] | None = None

    def _async_add_bed_presence_entity() -> None:
        """Add bed presence entity."""
        async_add_entities([WithingsBinarySensor(coordinator)])
        if callback:
            callback()

    if ent_reg.async_get_entity_id(
        Platform.BINARY_SENSOR, DOMAIN, f"withings_{entry.unique_id}_in_bed"
    ):
        _async_add_bed_presence_entity()
    else:
        callback = coordinator.async_add_listener(_async_add_bed_presence_entity)


class WithingsBinarySensor(WithingsEntity, BinarySensorEntity):
    """Implementation of a Withings sensor."""

    _attr_translation_key = "in_bed"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    coordinator: WithingsBedPresenceDataUpdateCoordinator

    def __init__(self, coordinator: WithingsBedPresenceDataUpdateCoordinator) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator, "in_bed")

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.in_bed
