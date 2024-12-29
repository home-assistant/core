"""Binary Sensor for VeSync."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.vesyncfan import VeSyncAirBypass
from pyvesync.vesyncoutlet import VeSyncOutlet
from pyvesync.vesyncswitch import VeSyncSwitch

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VS_FANS
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VeSyncBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes custom binary sensor entities."""

    is_on: Callable[[VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch], bool] | None = None
    on_icon: str | None = None
    off_icon: str | None = None


SENSOR_DESCRIPTIONS: tuple[VeSyncBinarySensorEntityDescription, ...] = (
    VeSyncBinarySensorEntityDescription(
        key="water_lacks",
        translation_key="water_lacks",
        is_on=lambda device: device.water_lacks == "on",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    VeSyncBinarySensorEntityDescription(
        key="is_on",
        translation_key="online",
        is_on=lambda device: device.is_on,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor platform."""
    entities: list[VeSyncBinarySensor] = []
    for device in hass.data[DOMAIN][VS_FANS]:
        for description in SENSOR_DESCRIPTIONS:
            if getattr(device, description.key, None) is not None:
                entities.append(VeSyncBinarySensor(description, device))  # noqa: PERF401
    async_add_entities(entities)


class VeSyncBinarySensor(BinarySensorEntity, VeSyncBaseEntity):
    """Hyundai / Kia Connect binary sensor class."""

    def __init__(
        self,
        description: VeSyncBinarySensorEntityDescription,
        device: VeSyncBaseEntity,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self.entity_description: VeSyncBinarySensorEntityDescription = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.entity_description.is_on is not None:
            return self.entity_description.is_on(self.device)
        return None

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if (
            self.entity_description.on_icon == self.entity_description.off_icon
        ) is None:
            return BinarySensorEntity.icon
        return (
            self.entity_description.on_icon
            if self.is_on
            else self.entity_description.off_icon
        )
