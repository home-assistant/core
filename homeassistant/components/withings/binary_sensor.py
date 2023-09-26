"""Sensors flow for Withings."""
from __future__ import annotations

from withings_api.common import NotifyAppli

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Measurement


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    user_id = str(entry.unique_id)

    async_add_entities([WithingSleepBinarySensor(user_id)])


# Scheduled for removal in 2024.4
class WithingSleepBinarySensor(BinarySensorEntity):
    """Implementation of a Withings sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "in_bed"
    _attr_icon = "mdi:bed"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, user_id: str) -> None:
        """Initialize sleep sensor."""
        self._user_id = user_id
        self._attr_unique_id = f"withings_{user_id}_{Measurement.IN_BED.value}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
            manufacturer="Withings",
        )

    async def async_added_to_hass(self) -> None:
        """Listen to events after being added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"withings_{self._user_id}_sleep", self.handle_event
            )
        )

    @callback
    def handle_event(self, notification_type: NotifyAppli) -> None:
        """Handle received event."""
        self._attr_is_on = notification_type == NotifyAppli.BED_IN
        self.async_write_ha_state()
