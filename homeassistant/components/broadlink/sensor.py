"""Support for Broadlink sensors."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_HOST, PERCENTAGE, POWER_WATT, TEMP_CELSIUS
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .entity import BroadlinkEntity
from .helpers import import_device

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="air_quality",
        name="Air Quality",
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="light",
        name="Light",
        device_class=DEVICE_CLASS_ILLUMINANCE,
    ),
    SensorEntityDescription(
        key="noise",
        name="Noise",
    ),
    SensorEntityDescription(
        key="power",
        name="Current power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string}, extra=vol.ALLOW_EXTRA
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the device and discontinue platform.

    This is for backward compatibility.
    Do not use this method.
    """
    import_device(hass, config[CONF_HOST])
    _LOGGER.warning(
        "The sensor platform is deprecated, please remove it from your configuration"
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink sensor."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    sensor_data = device.update_manager.coordinator.data
    sensors = [
        BroadlinkSensor(device, description)
        for description in SENSOR_TYPES
        if description.key in sensor_data
        and (
            # These devices have optional sensors.
            # We don't create entities if the value is 0.
            sensor_data[description.key] != 0
            or device.api.type not in {"RM4PRO", "RM4MINI"}
        )
    ]
    async_add_entities(sensors)


class BroadlinkSensor(BroadlinkEntity, SensorEntity):
    """Representation of a Broadlink sensor."""

    def __init__(self, device, description: SensorEntityDescription):
        """Initialize the sensor."""
        super().__init__(device)
        self.entity_description = description

        self._attr_name = f"{device.name} {description.name}"
        self._attr_native_value = self._coordinator.data[description.key]
        self._attr_unique_id = f"{device.unique_id}-{description.key}"

    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_native_value = data[self.entity_description.key]
