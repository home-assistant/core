"""Matter lock."""
from __future__ import annotations

from enum import IntFlag
from typing import Any

from chip.clusters import Objects as clusters

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LOGGER
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

    features: int | None = None

    @property
    def supports_door_position_sensor(self) -> bool:
        """Return True if the lock supports door position sensor."""
        if self.features is None:
            return False

        return bool(self.features & DoorLockFeature.kDoorPositionSensor)

    async def send_device_command(
        self,
        command: clusters.ClusterCommand,
        timed_request_timeout_ms: int = 1000,
    ) -> None:
        """Send a command to the device."""
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=command,
            timed_request_timeout_ms=timed_request_timeout_ms,
        )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock with pin if needed."""
        await self.send_device_command(command=clusters.DoorLock.Commands.LockDoor())

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock with pin if needed."""
        await self.send_device_command(command=clusters.DoorLock.Commands.UnlockDoor())

    @callback
    def _update_from_device(self) -> None:
        """Update the entity from the device."""

        if self.features is None:
            self.features = int(
                self.get_matter_attribute_value(clusters.DoorLock.Attributes.FeatureMap)
            )

        lock_state = self.get_matter_attribute_value(
            clusters.DoorLock.Attributes.LockState
        )

        LOGGER.debug("Lock state: %s for %s", lock_state, self.entity_id)

        if lock_state is clusters.DoorLock.Enums.DlLockState.kLocked:
            self._attr_is_locked = True
            self._attr_is_locking = False
            self._attr_is_unlocking = False
        elif lock_state is clusters.DoorLock.Enums.DlLockState.kUnlocked:
            self._attr_is_locked = False
            self._attr_is_locking = False
            self._attr_is_unlocking = False
        elif lock_state is clusters.DoorLock.Enums.DlLockState.kNotFullyLocked:
            if self.is_locked is True:
                self._attr_is_unlocking = True
            elif self.is_locked is False:
                self._attr_is_locking = True
        else:
            # According to the matter docs a null state can happen during device startup.
            self._attr_is_locked = None
            self._attr_is_locking = None
            self._attr_is_unlocking = None

        if self.supports_door_position_sensor:
            door_state = self.get_matter_attribute_value(
                clusters.DoorLock.Attributes.DoorState
            )

            assert door_state is not None

            LOGGER.debug("Door state: %s for %s", door_state, self.entity_id)

            self._attr_is_jammed = (
                door_state is clusters.DoorLock.Enums.DlDoorState.kDoorJammed
            )


class DoorLockFeature(IntFlag):
    """Temp enum that represents the features of a door lock.

    Should be replaced by the library provided one once that is released.
    """

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
        required_attributes=(clusters.DoorLock.Attributes.LockState,),
        optional_attributes=(clusters.DoorLock.Attributes.DoorState,),
    ),
]
