"""Integration for SFTP Storage."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
import errno
import logging
from pathlib import Path

from homeassistant.components.backup import BackupAgentError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .client import BackupAgentClient
from .const import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
    LOGGER,
)

type SFTPConfigEntry = ConfigEntry[SFTPConfigEntryData]


@dataclass(kw_only=True)
class SFTPConfigEntryData:
    """Dataclass holding all config entry data for an SFTP Storage entry."""

    host: str
    port: int
    username: str
    password: str | None = field(repr=False)
    private_key_file: str | None
    backup_location: str


async def async_setup_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Set up SFTP Storage from a config entry."""

    cfg = SFTPConfigEntryData(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data.get(CONF_PASSWORD),
        private_key_file=entry.data.get(CONF_PRIVATE_KEY_FILE, []),
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

    def remove_files(entry: SFTPConfigEntry) -> None:
        pkey = Path(entry.data[CONF_PRIVATE_KEY_FILE])

        if pkey.exists():
            LOGGER.debug(
                "Removing private key (%s) for %s integration for host %s@%s",
                pkey,
                DOMAIN,
                entry.data[CONF_USERNAME],
                entry.data[CONF_HOST],
            )
            try:
                pkey.unlink()
            except OSError as e:
                LOGGER.warning(
                    "Failed to remove private key %s for %s integration for host %s@%s. %s",
                    pkey.name,
                    DOMAIN,
                    entry.data[CONF_USERNAME],
                    entry.data[CONF_HOST],
                    str(e),
                )

        try:
            pkey.parent.rmdir()
        except OSError as e:
            if e.errno == errno.ENOTEMPTY:  # Directory not empty
                if LOGGER.isEnabledFor(logging.DEBUG):
                    leftover_files = []
                    # If we get an exception while gathering leftover files, make sure to log plain message.
                    with contextlib.suppress(OSError):
                        leftover_files = [f.name for f in pkey.parent.iterdir()]

                    LOGGER.debug(
                        "Storage directory for %s integration is not empty (%s)%s",
                        DOMAIN,
                        str(pkey.parent),
                        f", files: {', '.join(leftover_files)}"
                        if leftover_files
                        else "",
                    )
            else:
                LOGGER.warning(
                    "Error occurred while removing directory %s for integration %s: %s at host %s@%s",
                    str(pkey.parent),
                    DOMAIN,
                    str(e),
                    entry.data[CONF_USERNAME],
                    entry.data[CONF_HOST],
                )
        else:
            LOGGER.debug(
                "Removed storage directory for %s integration",
                DOMAIN,
                entry.data[CONF_USERNAME],
                entry.data[CONF_HOST],
            )

    if bool(entry.data.get(CONF_PRIVATE_KEY_FILE)):
        LOGGER.debug(
            "Cleaning up after %s integration for host %s@%s",
            DOMAIN,
            entry.data[CONF_USERNAME],
            entry.data[CONF_HOST],
        )
        await hass.async_add_executor_job(remove_files, entry)


async def async_unload_entry(hass: HomeAssistant, entry: SFTPConfigEntry) -> bool:
    """Unload SFTP Storage config entry."""
    LOGGER.debug(
        "Unloading %s integration for host %s@%s",
        DOMAIN,
        entry.data[CONF_USERNAME],
        entry.data[CONF_HOST],
    )
    return True
