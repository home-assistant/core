"""Support for Abode Security System sensors."""
from __future__ import annotations

import abodepy.helpers.constants as CONST

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
)

from . import AbodeDevice
from .const import DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CONST.TEMP_STATUS_KEY,
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key=CONST.HUMI_STATUS_KEY,
        name="Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    SensorEntityDescription(
        key=CONST.LUX_STATUS_KEY,
        name="Lux",
        device_class=DEVICE_CLASS_ILLUMINANCE,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Abode sensor devices."""
    data = hass.data[DOMAIN]

    entities = []

    for device in data.abode.get_devices(generic_type=CONST.TYPE_SENSOR):
        conditions = device.get_value(CONST.STATUSES_KEY)
        entities.extend(
            [
                AbodeSensor(data, device, description)
                for description in SENSOR_TYPES
                if description.key in conditions
            ]
        )

    async_add_entities(entities)


class AbodeSensor(AbodeDevice, SensorEntity):
    """A sensor implementation for Abode devices."""

    def __init__(self, data, device, description: SensorEntityDescription):
        """Initialize a sensor for an Abode device."""
        super().__init__(data, device)
        self.entity_description = description
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{device.device_uuid}-{description.key}"
        if description.key == CONST.TEMP_STATUS_KEY:
            self._attr_native_unit_of_measurement = device.temp_unit
        elif description.key == CONST.HUMI_STATUS_KEY:
            self._attr_native_unit_of_measurement = device.humidity_unit
        elif description.key == CONST.LUX_STATUS_KEY:
            self._attr_native_unit_of_measurement = device.lux_unit

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key == CONST.TEMP_STATUS_KEY:
            return self._device.temp
        if self.entity_description.key == CONST.HUMI_STATUS_KEY:
            return self._device.humidity
        if self.entity_description.key == CONST.LUX_STATUS_KEY:
            return self._device.lux
