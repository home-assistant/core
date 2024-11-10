"""Platform for binary sensor integration."""

from __future__ import annotations

import dataclasses

from aioccl import CCLDevice, CCLSensor, CCLSensorTypes

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CCLEntity

CCL_BINARY_SENSOR_DESCRIPTIONS: dict[str, BinarySensorEntityDescription] = {
    CCLSensorTypes.BATTERY_BINARY: BinarySensorEntityDescription(
        key="BATTERY_BINARY",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    CCLSensorTypes.CONNECTION: BinarySensorEntityDescription(
        key="CONNECTION",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config entry in HA."""
    device: CCLDevice = entry.runtime_data

    def _new_binary_sensor(sensor: CCLSensor) -> None:
        """Add a binary sensor to the data entry."""
        entity_description = dataclasses.replace(
            CCL_BINARY_SENSOR_DESCRIPTIONS[sensor.sensor_type],
            key=sensor.key,
            name=sensor.name,
        )
        async_add_entities([CCLBinarySensorEntity(sensor, device, entity_description)])

    device.register_new_binary_sensor_cb(_new_binary_sensor)
    entry.async_on_unload(
        lambda: device.remove_new_binary_sensor_cb(_new_binary_sensor)
    )

    for sensor in device.binary_sensors.values():
        _new_binary_sensor(sensor)


class CCLBinarySensorEntity(CCLEntity, BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        internal: CCLSensor,
        device: CCLDevice,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a CCL Sensor Entity."""
        super().__init__(internal, device)

        self.entity_description = entity_description

    @property
    def is_on(self) -> None | bool:
        """Return the state of the sensor."""
        return bool(self._internal.value)
