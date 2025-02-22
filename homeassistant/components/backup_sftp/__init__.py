"""Integration for SFTP Backup Storage."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .client import BackupAgentClient
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PRIVATE_KEY_FILE,
    CONF_BACKUP_LOCATION,
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


async def async_setup_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Set up SFTP client from a config entry."""

    cfg = SFTPConfigEntryData(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data.get(CONF_PASSWORD),
        private_key_file=entry.data.get(CONF_PRIVATE_KEY_FILE),
        backup_location=entry.data.get(CONF_BACKUP_LOCATION),
    )
    entry.runtime_data = cfg

    # Check if we can list directory items during setup.
    # This will raise exception if where is something either wrong
    # with SSH server or config.
    try:
        async with BackupAgentClient(cfg) as client:
            assert isinstance(await client.list_backup_location(), list)
    except Exception as e:
        raise ConfigEntryNotReady from e

    # Notify backup listeners
    _async_notify_backup_listeners_soon(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Unload SFTP config entry."""
    _async_notify_backup_listeners_soon(hass)
    return True


def _async_notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()


@callback
def _async_notify_backup_listeners_soon(hass: HomeAssistant) -> None:
    hass.loop.call_soon(_async_notify_backup_listeners, hass)
