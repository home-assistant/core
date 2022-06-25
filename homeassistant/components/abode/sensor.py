"""Support for Abode Security System sensors."""
from __future__ import annotations

from typing import cast

from abodepy.devices.sensor import CONST, AbodeSensor as AbodeSense

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbodeDevice, AbodeSystem
from .const import DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CONST.TEMP_STATUS_KEY,
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key=CONST.HUMI_STATUS_KEY,
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key=CONST.LUX_STATUS_KEY,
        name="Lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Abode sensor devices."""
    data: AbodeSystem = hass.data[DOMAIN]

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

    _device: AbodeSense

    def __init__(
        self,
        data: AbodeSystem,
        device: AbodeSense,
        description: SensorEntityDescription,
    ) -> None:
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
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.entity_description.key == CONST.TEMP_STATUS_KEY:
            return cast(float, self._device.temp)
        if self.entity_description.key == CONST.HUMI_STATUS_KEY:
            return cast(float, self._device.humidity)
        if self.entity_description.key == CONST.LUX_STATUS_KEY:
            return cast(float, self._device.lux)
        return None
