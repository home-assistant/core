"""Support for Daikin AC sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydaikin.daikin_base import Appliance

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_KILO_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as DAIKIN_DOMAIN, DaikinApi
from .const import (
    ATTR_ALL_ENERGY_TODAY,
    ATTR_ALL_POWER,
    ATTR_COMPRESSOR_FREQUENCY,
    ATTR_COOL_ENERGY,
    ATTR_ENERGY_TODAY,
    ATTR_HEAT_ENERGY,
    ATTR_HUMIDITY,
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
    ATTR_TARGET_HUMIDITY,
)


@dataclass
class DaikinRequiredKeysMixin:
    """Mixin for required keys."""

    value_func: Callable[[Appliance], float | None]
    cross_device: bool  # Cross-device sensors should be created only once


@dataclass
class DaikinSensorEntityDescription(SensorEntityDescription, DaikinRequiredKeysMixin):
    """Describes Daikin sensor entity."""


SENSOR_TYPES: tuple[DaikinSensorEntityDescription, ...] = (
    DaikinSensorEntityDescription(
        key=ATTR_INSIDE_TEMPERATURE,
        name="Inside Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        entity_registry_enabled_default=True,
        value_func=lambda device: device.inside_temperature,
        cross_device=False,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_OUTSIDE_TEMPERATURE,
        name="Outside Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        entity_registry_enabled_default=True,
        value_func=lambda device: device.outside_temperature,
        cross_device=True,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_HUMIDITY,
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=True,
        value_func=lambda device: device.humidity,
        cross_device=False,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_TARGET_HUMIDITY,
        name="Target Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=True,
        value_func=lambda device: device.humidity,
        cross_device=False,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_ALL_POWER,
        name="All Devices' Estimated Power Consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=POWER_KILO_WATT,
        entity_registry_enabled_default=True,
        value_func=lambda device: round(device.current_total_power_consumption, 2),
        cross_device=True,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_COOL_ENERGY,
        name="Cool Energy Consumption",
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        value_func=lambda device: round(device.last_hour_cool_energy_consumption, 2),
        cross_device=False,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_HEAT_ENERGY,
        name="Heat Energy Consumption",
        icon="mdi:fire",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        value_func=lambda device: round(device.last_hour_heat_energy_consumption, 2),
        cross_device=False,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_ENERGY_TODAY,
        name="Energy Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        value_func=lambda device: round(device.today_energy_consumption, 2),
        cross_device=False,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_COMPRESSOR_FREQUENCY,
        name="Compressor Frequency",
        icon="mdi:fan",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=FREQUENCY_HERTZ,
        entity_registry_enabled_default=False,
        value_func=lambda device: device.compressor_frequency,
        cross_device=True,
    ),
    DaikinSensorEntityDescription(
        key=ATTR_ALL_ENERGY_TODAY,
        name="All Devices' Energy Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        value_func=lambda device: round(device.today_total_energy_consumption, 2),
        cross_device=True,
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Old way of setting up the Daikin sensors.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Daikin climate based on config_entry."""
    daikin_api = hass.data[DAIKIN_DOMAIN].get(entry.entry_id)
    sensors = [ATTR_INSIDE_TEMPERATURE]
    if daikin_api.device.support_outside_temperature:
        sensors.append(ATTR_OUTSIDE_TEMPERATURE)
    if daikin_api.device.support_energy_consumption:
        sensors.append(ATTR_ENERGY_TODAY)
        sensors.append(ATTR_COOL_ENERGY)
        sensors.append(ATTR_HEAT_ENERGY)
        sensors.append(ATTR_ALL_POWER)
        sensors.append(ATTR_ALL_ENERGY_TODAY)
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
        if not description.cross_device:
            self._attr_name = f"{api.name} {description.name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self.entity_description.cross_device:
            # Cross-device sensors should be generated once for all devices
            return self.entity_description.key
        return f"{self._api.device.mac}-{self.entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self._api.device)

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return self._api.device_info
