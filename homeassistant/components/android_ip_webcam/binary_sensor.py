"""Support for Android IP Webcam binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MOTION_ACTIVE
from .coordinator import AndroidIPCamConfigEntry, AndroidIPCamDataUpdateCoordinator
from .entity import AndroidIPCamBaseEntity

BINARY_SENSOR_DESCRIPTION = BinarySensorEntityDescription(
    key="motion_active",
    name="Motion active",
    device_class=BinarySensorDeviceClass.MOTION,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AndroidIPCamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the IP Webcam sensors from config entry."""

    async_add_entities([IPWebcamBinarySensor(config_entry.runtime_data)])


class IPWebcamBinarySensor(AndroidIPCamBaseEntity, BinarySensorEntity):
    """Representation of an IP Webcam binary sensor."""

    def __init__(
        self,
        coordinator: AndroidIPCamDataUpdateCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = BINARY_SENSOR_DESCRIPTION
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{BINARY_SENSOR_DESCRIPTION.key}"
        )
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        """Return availability if setting is enabled."""
        return MOTION_ACTIVE in self.cam.enabled_sensors and super().available

    @property
    def is_on(self) -> bool:
        """Return if motion is detected."""
        return self.cam.get_sensor_value(MOTION_ACTIVE) == 1.0
