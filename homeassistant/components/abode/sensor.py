"""Support for Abode Security System sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from jaraco.abode.devices.sensor import Sensor
from jaraco.abode.helpers.constants import (
    HUMI_STATUS_KEY,
    LUX_STATUS_KEY,
    STATUSES_KEY,
    TEMP_STATUS_KEY,
    TYPE_SENSOR,
    UNIT_CELSIUS,
    UNIT_FAHRENHEIT,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbodeSystem
from .const import DOMAIN
from .entity import AbodeDevice

ABODE_TEMPERATURE_UNIT_HA_UNIT = {
    UNIT_FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
    UNIT_CELSIUS: UnitOfTemperature.CELSIUS,
}


@dataclass(frozen=True, kw_only=True)
class AbodeSensorDescription(SensorEntityDescription):
    """Class describing Abode sensor entities."""

    value_fn: Callable[[Sensor], float]
    native_unit_of_measurement_fn: Callable[[Sensor], str]


SENSOR_TYPES: tuple[AbodeSensorDescription, ...] = (
    AbodeSensorDescription(
        key=TEMP_STATUS_KEY,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement_fn=lambda device: ABODE_TEMPERATURE_UNIT_HA_UNIT[
            device.temp_unit
        ],
        value_fn=lambda device: cast(float, device.temp),
    ),
    AbodeSensorDescription(
        key=HUMI_STATUS_KEY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement_fn=lambda _: PERCENTAGE,
        value_fn=lambda device: cast(float, device.humidity),
    ),
    AbodeSensorDescription(
        key=LUX_STATUS_KEY,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement_fn=lambda _: LIGHT_LUX,
        value_fn=lambda device: cast(float, device.lux),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Abode sensor devices."""
    data: AbodeSystem = hass.data[DOMAIN]

    async_add_entities(
        AbodeSensor(data, device, description)
        for description in SENSOR_TYPES
        for device in data.abode.get_devices(generic_type=TYPE_SENSOR)
        if description.key in device.get_value(STATUSES_KEY)
    )


class AbodeSensor(AbodeDevice, SensorEntity):
    """A sensor implementation for Abode devices."""

    entity_description: AbodeSensorDescription
    _device: Sensor

    def __init__(
        self,
        data: AbodeSystem,
        device: Sensor,
        description: AbodeSensorDescription,
    ) -> None:
        """Initialize a sensor for an Abode device."""
        super().__init__(data, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.uuid}-{description.key}"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the native unit of measurement."""
        return self.entity_description.native_unit_of_measurement_fn(self._device)
