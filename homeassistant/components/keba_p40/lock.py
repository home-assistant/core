"""Lock platform for KEBA P40 (permanent socket lock)."""

from typing import Any

from keba_kecontact_p40 import KebaP40Error

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import KebaP40ConfigEntry
from .entity import KebaP40Entity

PARALLEL_UPDATES = 1

SOCKET_LOCK = LockEntityDescription(
    key="socket_lock",
    translation_key="socket_lock",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaP40ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA P40 socket lock."""
    async_add_entities([KebaP40Lock(entry.runtime_data, SOCKET_LOCK)])


class KebaP40Lock(KebaP40Entity, LockEntity):
    """Permanent socket lock for the KEBA P40."""

    @property
    def is_locked(self) -> bool | None:
        """Return True if the socket is permanently locked."""
        return self._wallbox.permanently_locked

    async def async_lock(self, **kwargs: Any) -> None:
        """Permanently lock the socket."""
        try:
            await self.coordinator.client.lock(self.coordinator.serial)
        except KebaP40Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the socket."""
        try:
            await self.coordinator.client.unlock(self.coordinator.serial)
        except KebaP40Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        await self.coordinator.async_request_refresh()
