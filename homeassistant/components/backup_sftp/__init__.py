"""Integration for SFTP Backup Storage."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.components.backup import BackupAgentError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.util import slugify

from .client import BackupAgentClient
from .const import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DATA_BACKUP_AGENT_LISTENERS,
)

type SFTPConfigEntry = ConfigEntry[SFTPConfigEntryData]


@dataclass(kw_only=True)
class SFTPConfigEntryData:
    """Dataclass holding all config entry data for an SFTP Backup Storage entry."""

    host: str
    port: int = 22
    username: str
    password: str | None = field(repr=False)
    private_key_file: str | None = ""
    backup_location: str

    @property
    def unique_id(self) -> str:
        """Return unique id for this config entry."""
        return slugify(
            ".".join(
                [
                    self.host,
                    str(self.port),
                    self.username,
                    self.backup_location,
                ]
            )
        )


async def async_setup_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Set up SFTP client from a config entry."""

    cfg = SFTPConfigEntryData(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data.get(CONF_PASSWORD),
        private_key_file=entry.data.get(CONF_PRIVATE_KEY_FILE),
        backup_location=entry.data[CONF_BACKUP_LOCATION],
    )
    entry.runtime_data = cfg

    # Check if we can list directory items during setup.
    # This will raise exception if there is something either wrong
    # with SSH server or config.
    try:
        async with BackupAgentClient(entry, hass) as client:
            if not isinstance(await client.list_backup_location(), list):
                raise ConfigEntryError("Unexpected error while setting up integration.")
    except BackupAgentError as e:
        raise ConfigEntryError from e

    # Notify backup listeners
    def _async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(_async_notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Unload SFTP config entry."""
    return True
