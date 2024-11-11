"""Platform for eq3 lock entities."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Eq3ConfigEntry
from .const import ENTITY_KEY_LOCK
from .entity import Eq3Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Eq3ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the entry."""

    async_add_entities(
        [Eq3LockEntity(entry)],
    )


class Eq3LockEntity(Eq3Entity, LockEntity):
    """Lock to prevent manual changes to the thermostat."""

    _attr_translation_key = ENTITY_KEY_LOCK

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the thermostat."""

        await self._thermostat.async_set_locked(True)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the thermostat."""

        await self._thermostat.async_set_locked(False)

    @property
    def is_locked(self) -> bool:
        """Whether the thermostat is locked."""

        if TYPE_CHECKING:
            assert self._thermostat.status is not None

        return self._thermostat.status.is_locked
