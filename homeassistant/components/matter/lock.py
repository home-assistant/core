"""Matter lock."""
from __future__ import annotations

from enum import IntFlag
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter lock from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.LOCK, async_add_entities)


class MatterLock(MatterEntity, LockEntity):
    """Representation of a Matter lock."""

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""

    @callback
    def _update_from_device(self) -> None:
        """Update the entity from the device."""


# Should be replaced with chip sdk enum once that is released
class DoorLockFeature(IntFlag):
    """Supported features of a Matter door lock."""

    kPinCredential = 0x1
    kRfidCredential = 0x2
    kFingerCredentials = 0x4
    kLogging = 0x8
    kWeekDayAccessSchedules = 0x10
    kDoorPositionSensor = 0x20
    kFaceCredentials = 0x40
    kCredentialsOverTheAirAccess = 0x80
    kUser = 0x100
    kNotification = 0x200
    kYearDayAccessSchedules = 0x400
    kHolidaySchedules = 0x800


DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.LOCK,
        entity_description=LockEntityDescription(key="MatterLock"),
        entity_class=MatterLock,
        required_attributes=(),
        optional_attributes=(),
    ),
]
