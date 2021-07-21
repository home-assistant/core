"""Support for Google Nest SDM sensors."""
from __future__ import annotations

import logging

from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import HumidityTrait, TemperatureTrait
from google_nest_sdm.exceptions import GoogleNestException

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

from .const import DATA_SUBSCRIBER, DOMAIN
from .device_info import DeviceInfo

_LOGGER = logging.getLogger(__name__)


DEVICE_TYPE_MAP = {
    "sdm.devices.types.CAMERA": "Camera",
    "sdm.devices.types.DISPLAY": "Display",
    "sdm.devices.types.DOORBELL": "Doorbell",
    "sdm.devices.types.THERMOSTAT": "Thermostat",
}


async def async_setup_sdm_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""

    subscriber = hass.data[DOMAIN][DATA_SUBSCRIBER]
    try:
        device_manager = await subscriber.async_get_device_manager()
    except GoogleNestException as err:
        _LOGGER.warning("Failed to get devices: %s", err)
        raise PlatformNotReady from err

    entities: list[SensorEntity] = []
    for device in device_manager.devices.values():
        if TemperatureTrait.NAME in device.traits:
            entities.append(TemperatureSensor(device))
        if HumidityTrait.NAME in device.traits:
            entities.append(HumiditySensor(device))
    async_add_entities(entities)


class SensorBase(SensorEntity):
    """Representation of a dynamically updated Sensor."""

    def __init__(self, device: Device) -> None:
        """Initialize the sensor."""
        self._device = device
        self._device_info = DeviceInfo(device)

    @property
    def should_poll(self) -> bool:
        """Disable polling since entities have state pushed via pubsub."""
        return False

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        # The API "name" field is a unique device identifier.
        return f"{self._device.name}-{self.device_class}"

    @property
    def device_info(self):
        """Return device specific attributes."""
        return self._device_info.device_info

    async def async_added_to_hass(self):
        """Run when entity is added to register update signal handler."""
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )


class TemperatureSensor(SensorBase):
    """Representation of a Temperature Sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_info.device_name} Temperature"

    @property
    def state(self):
        """Return the state of the sensor."""
        trait = self._device.traits[TemperatureTrait.NAME]
        return trait.ambient_temperature_celsius

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_TEMPERATURE


class HumiditySensor(SensorBase):
    """Representation of a Humidity Sensor."""

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        # The API returns the identifier under the name field.
        return f"{self._device.name}-humidity"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_info.device_name} Humidity"

    @property
    def state(self):
        """Return the state of the sensor."""
        trait = self._device.traits[HumidityTrait.NAME]
        return trait.ambient_humidity_percent

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_HUMIDITY
