"""Support for Android IP Webcam binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AndroidIPCamBaseEntity, AndroidIPCamDataUpdateCoordinator
from .const import DOMAIN, MOTION_ACTIVE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IP Webcam sensors from config entry."""

    coordinator: AndroidIPCamDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities([IPWebcamBinarySensor(coordinator)])


class IPWebcamBinarySensor(AndroidIPCamBaseEntity, BinarySensorEntity):
    """Representation of an IP Webcam binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        coordinator: AndroidIPCamDataUpdateCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.config_entry.data[CONF_NAME]} {MOTION_ACTIVE}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{MOTION_ACTIVE}"

    @property
    def available(self) -> bool:
        """Return avaibility if setting is enabled."""
        return MOTION_ACTIVE in self._ipcam.enabled_sensors and super().available

    @property
    def is_on(self) -> bool:
        """Return if motion is detected."""
        state, _ = self._ipcam.export_sensor(MOTION_ACTIVE)
        return state == 1.0
