"""Support for Google Nest SDM sensors."""
from __future__ import annotations

import logging

from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.device_traits import HumidityTrait, TemperatureTrait

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_DEVICE_MANAGER, DOMAIN
from .device_info import NestDeviceInfo

_LOGGER = logging.getLogger(__name__)


DEVICE_TYPE_MAP = {
    "sdm.devices.types.CAMERA": "Camera",
    "sdm.devices.types.DISPLAY": "Display",
    "sdm.devices.types.DOORBELL": "Doorbell",
    "sdm.devices.types.THERMOSTAT": "Thermostat",
}


async def async_setup_sdm_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""

    device_manager: DeviceManager = hass.data[DOMAIN][entry.entry_id][
        DATA_DEVICE_MANAGER
    ]
    entities: list[SensorEntity] = []
    for device in device_manager.devices.values():
        if TemperatureTrait.NAME in device.traits:
            entities.append(TemperatureSensor(device))
        if HumidityTrait.NAME in device.traits:
            entities.append(HumiditySensor(device))
    async_add_entities(entities)


class SensorBase(SensorEntity):
    """Representation of a dynamically updated Sensor."""

    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device: Device) -> None:
        """Initialize the sensor."""
        self._device = device
        self._device_info = NestDeviceInfo(device)
        self._attr_unique_id = f"{device.name}-{self.device_class}"
        self._attr_device_info = self._device_info.device_info

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to register update signal handler."""
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )


class TemperatureSensor(SensorBase):
    """Representation of a Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device_info.device_name} Temperature"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        trait: TemperatureTrait = self._device.traits[TemperatureTrait.NAME]
        # Round for display purposes because the API returns 5 decimal places.
        # This can be removed if the SDM API issue is fixed, or a frontend
        # display fix is added for all integrations.
        return float(round(trait.ambient_temperature_celsius, 1))


class HumiditySensor(SensorBase):
    """Representation of a Humidity Sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device_info.device_name} Humidity"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        trait: HumidityTrait = self._device.traits[HumidityTrait.NAME]
        # Cast without loss of precision because the API always returns an integer.
        return int(trait.ambient_humidity_percent)
