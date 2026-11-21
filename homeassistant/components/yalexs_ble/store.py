"""Storage for keypad credential slot names."""

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION = 1


def _async_get_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, dict]]:
    """Return the credential name store for a config entry."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.credentials")


class CredentialNames:
    """User supplied labels for keypad PIN slots."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the credential names."""
        self._hass = hass
        self._entry = entry
        self._store = _async_get_store(hass, entry.entry_id)
        self._names: dict[str, str] = {}

    async def async_load(self) -> None:
        """Load the names from storage."""
        if data := await self._store.async_load():
            self._names = data["names"]

    def get(self, slot: int) -> str | None:
        """Return the name for a slot."""
        return self._names.get(str(slot))

    async def async_set(self, slot: int, name: str) -> None:
        """Set the name for a slot."""
        self._names[str(slot)] = name
        await self._async_save()

    async def _async_save(self) -> None:
        """Save the names in an entry task, which unload waits for rather than cancels.

        Otherwise a cancelled save could finish writing after removal deleted the file.
        """
        task = self._entry.async_create_task(
            self._hass,
            self._store.async_save({"names": self._names}),
            "yalexs_ble save names",
        )
        await asyncio.shield(task)

    async def async_remove(self, slot: int) -> None:
        """Remove the name for a slot."""
        if self._names.pop(str(slot), None) is not None:
            await self._async_save()


async def async_remove_credential_names(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the stored names for a config entry."""
    await _async_get_store(hass, entry_id).async_remove()
