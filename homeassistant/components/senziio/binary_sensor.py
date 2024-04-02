"""Senziio binary sensor entities."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.mqtt import async_subscribe
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.json import json_loads_object

from .const import DOMAIN

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="presence",
        name="Presence",
        translation_key="presence",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="motion",
        name="Motion",
        translation_key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Senziio entities."""
    device = hass.data[DOMAIN][entry.entry_id]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.data["unique_id"])},
    )
    async_add_entities(
        [
            SenziioBinarySensorEntity(hass, entity_description, device_info, device)
            for entity_description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class SenziioBinarySensorEntity(BinarySensorEntity):
    """Senziio binary sensor entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_description: BinarySensorEntityDescription,
        device_info: DeviceInfo,
        device,
    ) -> None:
        """Initialize entity."""
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.id}_{entity_description.key}"
        self._attr_device_info = device_info
        self._hass = hass
        self._dt_topic = device.entity_topic(entity_description.key)

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT data event."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            data = json_loads_object(message.payload)
            self._attr_is_on = data.get(self.entity_description.key) is True
            self.async_write_ha_state()

        await async_subscribe(self._hass, self._dt_topic, message_received, 1)
