"""Platform for Sunricher DALI sensor entities."""

from __future__ import annotations

import logging

from PySrDaliGateway import CallbackEventType, Device
from PySrDaliGateway.helper import is_illuminance_sensor, is_motion_sensor
from PySrDaliGateway.types import IlluminanceStatus, MotionStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .entity import DaliDeviceEntity
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sunricher DALI sensor entities from config entry."""
    devices = entry.runtime_data.devices

    sensors: list[SensorEntity] = []
    for device in devices:
        if is_motion_sensor(device.dev_type):
            sensors.append(SunricherDaliMotionSensor(device))
        elif is_illuminance_sensor(device.dev_type):
            sensors.append(SunricherDaliIlluminanceSensor(device))

    if sensors:
        async_add_entities(sensors)


class SunricherDaliMotionSensor(DaliDeviceEntity, SensorEntity):
    """Representation of a Sunricher DALI Motion Sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["no_motion", "motion", "vacant", "presence", "occupancy"]
    _attr_name = None

    def __init__(self, device: Device) -> None:
        """Initialize the motion sensor."""
        super().__init__(device)
        self._device = device
        self._attr_native_value = "no_motion"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model,
            via_device=(DOMAIN, device.gw_sn),
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.MOTION_STATUS, self._handle_motion_status
            )
        )

        self._device.read_status()

    @callback
    def _handle_motion_status(self, status: MotionStatus) -> None:
        """Handle motion status updates."""
        motion_state = status["motion_state"]
        self._attr_native_value = motion_state.value
        self.schedule_update_ha_state()


class SunricherDaliIlluminanceSensor(DaliDeviceEntity, SensorEntity):
    """Representation of a Sunricher DALI Illuminance Sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_name = None

    def __init__(self, device: Device) -> None:
        """Initialize the illuminance sensor."""
        super().__init__(device)
        self._device = device
        self._illuminance_value: float | None = None
        self._sensor_enabled: bool = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.model,
            via_device=(DOMAIN, device.gw_sn),
        )

    @property
    def native_value(self) -> float | None:
        """Return the native value, or None if sensor is disabled."""
        if not self._sensor_enabled:
            return None
        return self._illuminance_value

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.ILLUMINANCE_STATUS, self._handle_illuminance_status
            )
        )

        self.async_on_remove(
            self._device.register_listener(
                CallbackEventType.SENSOR_ON_OFF, self._handle_sensor_on_off
            )
        )

        self._device.read_status()

    @callback
    def _handle_illuminance_status(self, status: IlluminanceStatus) -> None:
        """Handle illuminance status updates."""
        illuminance_value = status["illuminance_value"]
        is_valid = status["is_valid"]

        if not is_valid:
            _LOGGER.debug(
                "Illuminance value is not valid for device %s: %s lux",
                self._device.dev_id,
                illuminance_value,
            )
            return

        self._illuminance_value = illuminance_value
        self.schedule_update_ha_state()

    @callback
    def _handle_sensor_on_off(self, on_off: bool) -> None:
        """Handle sensor on/off updates."""
        self._sensor_enabled = on_off
        _LOGGER.debug(
            "Illuminance sensor enable state for device %s updated to: %s",
            self._device.dev_id,
            on_off,
        )
        self.schedule_update_ha_state()
