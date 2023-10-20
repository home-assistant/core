"""Tedee lock entities."""
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pytedee_async import TedeeClientException

from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
    LockEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_CHARGING, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CONNECTED,
    ATTR_DURATION_PULLSPRING,
    ATTR_NUMERIC_STATE,
    ATTR_SEMI_LOCKED,
    ATTR_SUPPORT_PULLSPING,
    CONF_UNLOCK_PULLS_LATCH,
    DOMAIN,
)
from .entity import TedeeEntity, TedeeEntityDescription


@dataclass
class TedeeLockEntityDescriptionMixin:
    """Extends Tedee lock entity description."""


@dataclass
class TedeeLockEntityDescription(
    LockEntityDescription, TedeeEntityDescription, TedeeLockEntityDescriptionMixin
):
    """Describes Tedee lock entity."""


ENTITIES: tuple[TedeeLockEntityDescription, ...] = (
    TedeeLockEntityDescription(
        unique_id_fn=lambda lock: f"{lock.lock_id}-lock",
        key="lock",
        translation_key="lock",
        icon="mdi:lock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tedee lock entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[TedeeLockEntity] = []
    for lock in coordinator.data.values():
        for entity_description in ENTITIES:
            if lock.is_enabled_pullspring:
                entities.append(
                    TedeeLockWithLatchEntity(
                        lock, coordinator, entity_description, entry
                    )
                )
            else:
                entities.append(
                    TedeeLockEntity(lock, coordinator, entity_description, entry)
                )

    async_add_entities(entities)


class TedeeLockEntity(TedeeEntity, LockEntity):
    """A tedee lock that doesn't have pullspring enabled."""

    entity_description: TedeeLockEntityDescription

    def __init__(self, lock, coordinator, entity_description, entry) -> None:
        """Initialize the lock."""
        super().__init__(lock, coordinator, entity_description)
        self._unlock_pulls_latch = entry.data.get(CONF_UNLOCK_PULLS_LATCH, False)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._lock.state == 6

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self._lock.state == 4

    @property
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        return self._lock.state == 5

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._lock.is_state_jammed

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Extra attributes for the lock."""
        attributes = {
            ATTR_ID: self._lock.lock_id,
            ATTR_NUMERIC_STATE: self._lock.state,
            ATTR_CONNECTED: self._lock.is_connected,
            ATTR_SUPPORT_PULLSPING: self._lock.is_enabled_pullspring,
            ATTR_SEMI_LOCKED: self._lock.state == 3,
        }
        if self._lock.lock_type == "Tedee PRO":  # only pro has rechargeable battery
            attributes |= {ATTR_BATTERY_CHARGING: self._lock.is_charging}

        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._lock.is_connected

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        try:
            self._lock.state = 4
            self.async_write_ha_state()

            if self._unlock_pulls_latch:
                await self.coordinator.tedee_client.open(self._lock.lock_id)
            else:
                await self.coordinator.tedee_client.unlock(self._lock.lock_id)
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            raise HomeAssistantError(
                "Failed to unlock the door. Lock %s" % self._lock.lock_id
            ) from ex

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door."""
        try:
            self._lock.state = 5
            self.async_write_ha_state()

            await self.coordinator.tedee_client.lock(self._lock.lock_id)
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            raise HomeAssistantError(
                "Failed to lock the door. Lock %s" % self._lock.lock_id
            ) from ex


class TedeeLockWithLatchEntity(TedeeLockEntity):
    """A tedee lock but has pullspring enabled, so it additional features."""

    @property
    def supported_features(self) -> LockEntityFeature:
        """Flag supported features."""
        return LockEntityFeature.OPEN

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Extra attributes for the lock."""
        return super().extra_state_attributes | {
            ATTR_DURATION_PULLSPRING: self._lock.duration_pullspring
        }

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door with pullspring."""
        try:
            self._lock.state = 4
            self.async_write_ha_state()

            await self.coordinator.tedee_client.open(self._lock.lock_id)
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            raise HomeAssistantError(
                "Failed to unlatch the door. Lock %s" % self._lock.lock_id
            ) from ex
