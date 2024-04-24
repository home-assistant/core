"""Support for Flo Water Monitor binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDeviceDataUpdateCoordinator
from .entity import FloEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flo sensors from config entry."""
    devices: list[FloDeviceDataUpdateCoordinator] = hass.data[FLO_DOMAIN][
        config_entry.entry_id
    ]["devices"]
    entities: list[BinarySensorEntity] = []
    for device in devices:
        if device.device_type == "puck_oem":
            # Flo "pucks" (leak detectors) *do* support pending alerts.
            # However these pending alerts mix unrelated issues like
            # low-battery alerts, humidity alerts, & temperature alerts
            # in addition to the critical "water detected" alert.
            #
            # Since there are non-binary sensors for battery, humidity,
            # and temperature, the binary sensor should only cover
            # water detection. If this sensor trips, you really have
            # a problem - vs. battery/temp/humidity which are warnings.
            entities.append(FloWaterDetectedBinarySensor(device))
        else:
            entities.append(FloPendingAlertsBinarySensor(device))
    async_add_entities(entities)


class FloPendingAlertsBinarySensor(FloEntity, BinarySensorEntity):
    """Binary sensor that reports on if there are any pending system alerts."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "pending_system_alerts"

    def __init__(self, device):
        """Initialize the pending alerts binary sensor."""
        super().__init__("pending_system_alerts", device)

    @property
    def is_on(self):
        """Return true if the Flo device has pending alerts."""
        return self._device.has_alerts

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self._device.has_alerts:
            return {}
        return {
            "info": self._device.pending_info_alerts_count,
            "warning": self._device.pending_warning_alerts_count,
            "critical": self._device.pending_critical_alerts_count,
        }


class FloWaterDetectedBinarySensor(FloEntity, BinarySensorEntity):
    """Binary sensor that reports if water is detected (for leak detectors)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "water_detected"

    def __init__(self, device):
        """Initialize the pending alerts binary sensor."""
        super().__init__("water_detected", device)

    @property
    def is_on(self):
        """Return true if the Flo device is detecting water."""
        return self._device.water_detected
