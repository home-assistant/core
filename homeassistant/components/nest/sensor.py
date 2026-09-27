"""Support for Google Nest SDM sensors."""

from datetime import datetime
import logging
from typing import override

from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import FanTrait, HumidityTrait, TemperatureTrait

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device_info import NestDeviceInfo
from .types import NestConfigEntry

_LOGGER = logging.getLogger(__name__)


DEVICE_TYPE_MAP = {
    "sdm.devices.types.CAMERA": "Camera",
    "sdm.devices.types.DISPLAY": "Display",
    "sdm.devices.types.DOORBELL": "Doorbell",
    "sdm.devices.types.THERMOSTAT": "Thermostat",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""

    def devices_added(devices: list[Device]) -> None:
        entities: list[SensorEntity] = []
        for device in devices:
            if TemperatureTrait.NAME in device.traits:
                entities.append(TemperatureSensor(device))
            if HumidityTrait.NAME in device.traits:
                entities.append(HumiditySensor(device))
            if (
                FanTrait.NAME in device.traits
                and device.traits[FanTrait.NAME].timer_mode is not None
            ):
                entities.append(FanTimerSensor(device))
        async_add_entities(entities)

    entry.runtime_data.register_devices_listener(devices_added)


class SensorBase(SensorEntity):
    """Representation of a dynamically updated Sensor."""

    _attr_should_poll = False
    _attr_state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(self, device: Device) -> None:
        """Initialize the sensor."""
        self._device = device
        self._device_info = NestDeviceInfo(device)
        self._attr_device_info = self._device_info.device_info

    @property
    @override
    def available(self) -> bool:
        """Return the device availability."""
        return self._device_info.available

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to register update signal handler."""
        self.async_on_remove(
            self._device.add_update_listener(self.async_write_ha_state)
        )


class TemperatureSensor(SensorBase):
    """Representation of a Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, device: Device) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{device.name}-temperature"

    @property
    @override
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

    def __init__(self, device: Device) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{device.name}-humidity"

    @property
    @override
    def native_value(self) -> int:
        """Return the state of the sensor."""
        trait: HumidityTrait = self._device.traits[HumidityTrait.NAME]
        # Cast without loss of precision because the API always returns an integer.
        return int(trait.ambient_humidity_percent)


class FanTimerSensor(SensorBase):
    """Representation of the Fan Timer Timeout Sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_state_class = None
    _attr_translation_key = "fan_timer_timeout"

    def __init__(self, device: Device) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{device.name}-fan-timer"

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        trait: FanTrait = self._device.traits[FanTrait.NAME]
        return trait.timer_timeout
