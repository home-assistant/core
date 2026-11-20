"""Legacy hassio storage helpers for migration.

Deprecated in 2026.8; keep only for one-way migration into config entries.
"""

from typing import Required, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 1


class StoredHassioUpdateConfig(TypedDict):
    """Represent legacy stored update configuration."""

    add_on_backup_before_update: bool
    add_on_backup_retain_copies: int
    core_backup_before_update: bool


class StoredHassioConfig(TypedDict, total=False):
    """Represent the legacy hassio store payload."""

    hassio_user: Required[str | None]
    update_config: StoredHassioUpdateConfig


class HassioConfigStore:
    """Load/remove the legacy hassio store (deprecated in 2026.8)."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the legacy hassio config store."""
        self._store: Store[StoredHassioConfig] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_VERSION_MINOR,
        )

    async def async_load(self) -> StoredHassioConfig | None:
        """Load legacy hassio storage data."""
        return await self._store.async_load()

    async def async_remove(self) -> None:
        """Remove the legacy hassio storage file."""
        await self._store.async_remove()
