"""Support for KEBA charging station lock."""

from typing import Any, override

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KebaConfigEntry, KebaHandler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA charging station platform."""
    keba = entry.runtime_data

    locks = [KebaLock(keba, "Authentication", "authentication")]
    async_add_entities(locks)


class KebaLock(LockEntity):
    """The entity class for KEBA charging stations lock."""

    _attr_should_poll = False

    def __init__(self, keba: KebaHandler, name: str, entity_type: str) -> None:
        """Initialize the KEBA lock."""
        self._keba = keba
        self._attr_is_locked = True
        self._attr_name = f"{keba.device_name} {name}"
        self._attr_unique_id = f"{keba.device_id}_{entity_type}"

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock wallbox."""
        await self._keba.async_stop()

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock wallbox."""
        await self._keba.async_start()

    async def async_update(self) -> None:
        """Attempt to retrieve on off state from the switch."""
        self._attr_is_locked = self._keba.get_value("Authreq") == 1

    def update_callback(self) -> None:
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    @override
    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        self.async_on_remove(self._keba.add_update_listener(self.update_callback))
