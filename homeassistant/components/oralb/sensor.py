"""Platform for sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from oralb import OralB
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_MAC, CONF_NAME, PERCENTAGE, TIME_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=3)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_MAC): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    ble_device = bluetooth.async_ble_device_from_address(
        hass, entry.data[CONF_MAC], connectable=True
    )
    _LOGGER.info("OralB setup")
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find OralB device with address {entry.data[CONF_MAC]}"
        )
    if ble_device:
        _LOGGER.info("Found OralB toothbrush")
        orlb = OralB(ble_device)

    async_add_entities(
        [
            Battery(orlb),
            Status(orlb),
            BrushTime(orlb),
            Mode(orlb),
        ]
    )


class OralBSensor(SensorEntity):
    """Master class for inheriting on sensors."""

    def __init__(self, orlb):
        """Initialize a sensor."""
        self.orlb = orlb
        self._attr_unique_id = self.orlb.ble_device.address + self._attr_name

    async def async_update(self):
        """Read data from OralB."""
        await self.orlb.gatherdata()


class Battery(OralBSensor):
    """Representation of Battery sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_name = "OralB Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.orlb.result["battery"]


class Status(OralBSensor):
    """Representation of Status sensor."""

    _attr_name = "OralB Status"
    _attr_icon = "mdi:toothbrush-electric"

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.orlb.result["status"]


class BrushTime(OralBSensor):
    """Representation of BrushTime sensor."""

    _attr_native_unit_of_measurement = TIME_SECONDS
    _attr_name = "OralB Brush Time"
    _attr_icon = "mdi:timer-sand-complete"

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.orlb.result["brush_time"]


class Mode(OralBSensor):
    """Representation of Mode sensor."""

    _attr_name = "OralB Mode"
    _attr_icon = "mdi:tooth"

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.orlb.result["mode"]
