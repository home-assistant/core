"""Sensor entities for the Bang & Olufsen integration."""

from __future__ import annotations

from datetime import timedelta

from mozart_api.models import BatteryState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeoConfigEntry
from .const import CONNECTION_STATUS, DOMAIN, WebsocketNotification
from .entity import BeoEntity
from .util import supports_battery

SCAN_INTERVAL = timedelta(minutes=15)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BeoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sensor entities from config entry."""
    entities: list[BeoSensor] = []

    # Check for Mozart device with battery
    if await supports_battery(config_entry.runtime_data.client):
        entities.append(BeoSensorBatteryLevel(config_entry))

    async_add_entities(entities, update_before_add=True)


class BeoSensor(SensorEntity, BeoEntity):
    """Base Bang & Olufsen Sensor."""

    def __init__(self, config_entry: BeoConfigEntry) -> None:
        """Initialize Sensor."""
        super().__init__(config_entry, config_entry.runtime_data.client)


class BeoSensorBatteryLevel(BeoSensor):
    """Battery level Sensor for Mozart devices."""

    _attr_native_unit_of_measurement = "%"
    _attr_translation_key = "battery_level"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, config_entry: BeoConfigEntry) -> None:
        """Init the battery level Sensor."""
        super().__init__(config_entry)

        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_unique_id = f"{self._unique_id}_battery_level"

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._unique_id}_{CONNECTION_STATUS}",
                self._async_update_connection_state,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._unique_id}_{WebsocketNotification.BATTERY}",
                self._update_battery,
            )
        )

    async def _update_battery(self, data: BatteryState) -> None:
        """Update sensor value."""
        self._attr_native_value = data.battery_level
        self.async_write_ha_state()
