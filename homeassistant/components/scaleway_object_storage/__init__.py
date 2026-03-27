"""The Scaleway Object Storage integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import aiohttp_client

if TYPE_CHECKING:
    from aiohttp_s3_client import S3Client

    from homeassistant.core import HomeAssistant

from . import exceptions, helpers
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

type ScalewayConfigEntry = ConfigEntry[S3Client]


async def async_setup_entry(hass: HomeAssistant, entry: ScalewayConfigEntry) -> bool:
    """Set up an integration config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    try:
        await helpers.check_connection(session, entry.data)
    except ConfigEntryNotReady, ConfigEntryError, ConfigEntryAuthFailed:
        # Re-raise as they are
        raise
    except exceptions.ScalewayException as e:
        # All other exceptions are translated
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key=e.translation_key,
            translation_placeholders=e.translation_placeholders,
        ) from e

    entry.runtime_data = helpers.create_client(session, entry.data)

    # Notify backup listeners
    def notify_backup_listeners() -> None:
        listeners = hass.data.get(DATA_BACKUP_AGENT_LISTENERS, [])
        for listener in list(listeners):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ScalewayConfigEntry) -> bool:
    """Unload a config entry."""
    return True
