"""Integration for SFTP Storage."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
import shutil

from homeassistant.components.backup import BackupAgentError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util import slugify

from .client import BackupAgentClient, get_client_keys
from .const import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DATA_BACKUP_AGENT_LISTENERS,
    LOGGER,
)

type SFTPConfigEntry = ConfigEntry[SFTPConfigEntryData]


@dataclass(kw_only=True)
class SFTPConfigEntryData:
    """Dataclass holding all config entry data for an SFTP Storage entry."""

    host: str
    port: int = 22
    username: str
    password: str | None = field(repr=False)
    private_key_file: list
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
    """Set up SFTP Storage from a config entry."""

    cfg = SFTPConfigEntryData(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data.get(CONF_PASSWORD),
        private_key_file=get_client_keys(hass),
        backup_location=entry.data[CONF_BACKUP_LOCATION],
    )
    entry.runtime_data = cfg

    # Establish a connection during setup.
    # This will raise exception if there is something wrong with either
    # SSH server or config.
    try:
        client = BackupAgentClient(entry, hass)
        await client.open()
    except BackupAgentError as e:
        raise ConfigEntryError from e

    # Notify backup listeners
    def _async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(_async_notify_backup_listeners))

    return True


async def async_remove_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> None:
    """Remove an SFTP Storage config entry."""

    def remove_files(storage_dir: Path) -> None:
        # For some reason, rmtree's `ignore_errors` would not ignore these exceptions
        # So we call with contextlib.suppress
        with contextlib.suppress(OSError, TypeError, ValueError, NotImplementedError):
            shutil.rmtree(storage_dir)
        LOGGER.debug("Removed storage directory for %s", entry.unique_id)

    if bool(entry.data.get(CONF_PRIVATE_KEY_FILE)):
        LOGGER.debug("Cleaning up after %s. ", entry.unique_id)
        storage_dir = Path(hass.config.path(STORAGE_DIR))
        await hass.async_add_executor_job(remove_files, storage_dir)


async def async_unload_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Unload SFTP Storage config entry."""
    LOGGER.debug("Unloading integration: %s", entry.unique_id)
    return True
