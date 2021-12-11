"""Support for Daikin AC sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydaikin.daikin_base import Appliance

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_KILO_WATT,
    TEMP_CELSIUS,
)

from . import DOMAIN as DAIKIN_DOMAIN, DaikinApi
from .const import (
    ATTR_COMPRESSOR_FREQUENCY,
    ATTR_COOL_ENERGY,
    ATTR_HEAT_ENERGY,
    ATTR_HUMIDITY,
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
    ATTR_TARGET_HUMIDITY,
    ATTR_TOTAL_POWER,
)


@dataclass
class DaikinRequiredKeysMixin:
    """Mixin for required keys."""

    value_func: Callable[[Appliance], float | None]


@dataclass
class DaikinSensorEntityDescription(SensorEntityDescription, DaikinRequiredKeysMixin):
    """Describes Daikin sensor entity."""


SENSOR_TYPES: tuple[DaikinSensorEntityDescription, ...] = (
    DaikinSensorEntityDescription(
        key=ATTR_INSIDE_TEMPERATURE,
        name="Inside Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_func=lambda device: device.inside_temperature,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_OUTSIDE_TEMPERATURE,
        name="Outside Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_func=lambda device: device.outside_temperature,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_HUMIDITY,
        name="Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_func=lambda device: device.humidity,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_TARGET_HUMIDITY,
        name="Target Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_func=lambda device: device.humidity,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_TOTAL_POWER,
        name="Total Power Consumption",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_KILO_WATT,
        value_func=lambda device: round(device.current_total_power_consumption, 2),
    ),
    DaikinSensorEntityDescription(
        key=ATTR_COOL_ENERGY,
        name="Cool Energy Consumption",
        icon="mdi:snowflake",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_func=lambda device: round(device.last_hour_cool_energy_consumption, 2),
    ),
    DaikinSensorEntityDescription(
        key=ATTR_HEAT_ENERGY,
        name="Heat Energy Consumption",
        icon="mdi:fire",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        value_func=lambda device: round(device.last_hour_heat_energy_consumption, 2),
    ),
    DaikinSensorEntityDescription(
        key=ATTR_COMPRESSOR_FREQUENCY,
        name="Compressor Frequency",
        icon="mdi:fan",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        value_func=lambda device: device.compressor_frequency,
    ),
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up the Daikin sensors.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Daikin climate based on config_entry."""
    daikin_api = hass.data[DAIKIN_DOMAIN].get(entry.entry_id)
    sensors = [ATTR_INSIDE_TEMPERATURE]
    if daikin_api.device.support_outside_temperature:
        sensors.append(ATTR_OUTSIDE_TEMPERATURE)
    if daikin_api.device.support_energy_consumption:
        sensors.append(ATTR_TOTAL_POWER)
        sensors.append(ATTR_COOL_ENERGY)
        sensors.append(ATTR_HEAT_ENERGY)
    if daikin_api.device.support_humidity:
        sensors.append(ATTR_HUMIDITY)
        sensors.append(ATTR_TARGET_HUMIDITY)
    if daikin_api.device.support_compressor_frequency:
        sensors.append(ATTR_COMPRESSOR_FREQUENCY)

    entities = [
        DaikinSensor(daikin_api, description)
        for description in SENSOR_TYPES
        if description.key in sensors
    ]
    async_add_entities(entities)


class DaikinSensor(SensorEntity):
    """Representation of a Sensor."""

    entity_description: DaikinSensorEntityDescription

    def __init__(
        self, api: DaikinApi, description: DaikinSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._api = api
        self._attr_name = f"{api.name} {description.name}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.device.mac}-{self.entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self._api.device)

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info
