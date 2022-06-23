"""Support for KEBA charging station switch."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the KEBA charging station platform."""
    if discovery_info is None:
        return

    keba = hass.data[DOMAIN]

    sensors = [KebaLock(keba, "Authentication", "authentication")]
    async_add_entities(sensors)


class KebaLock(LockEntity):
    """The entity class for KEBA charging stations switch."""

    def __init__(self, keba, name, entity_type):
        """Initialize the KEBA switch."""
        self._keba = keba
        self._name = name
        self._entity_type = entity_type
        self._state = True

    @property
    def should_poll(self):
        """Deactivate polling. Data updated by KebaHandler."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the lock."""
        return f"{self._keba.device_id}_{self._entity_type}"

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._keba.device_name} {self._name}"

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock wallbox."""
        await self._keba.async_stop()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock wallbox."""
        await self._keba.async_start()

    async def async_update(self):
        """Attempt to retrieve on off state from the switch."""
        self._state = self._keba.get_value("Authreq") == 1

    def update_callback(self):
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add update callback after being added to hass."""
        self._keba.add_update_listener(self.update_callback)
