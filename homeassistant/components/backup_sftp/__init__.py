"""Integration for SFTP Backup Storage."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import SSHClient
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PRIVATE_KEY_FILE,
    DATA_BACKUP_AGENT_LISTENERS,
)

type SFTPConfigEntry = ConfigEntry["SFTPConfigEntryData"]


@dataclass(kw_only=True)
class SFTPConfigEntryData:
    """Dataclass holding all config entry data for an SFTP Backup Storage entry."""

    host: str
    port: int = 22
    username: str
    password: str = ""
    private_key_file: str = ""
    backup_location: str = ""

    def client(self):
        """Return SSHClient when called."""

        return SSHClient(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            private_key_file=self.private_key_file,
        )


async def async_setup_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Set up SFTP client from a config entry."""

    cfg = SFTPConfigEntryData(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data.get(CONF_PASSWORD),
        private_key_file=entry.data.get(CONF_PRIVATE_KEY_FILE),
    )
    entry.runtime_data = cfg

    # Notify backup listeners
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Unload SFTP config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
