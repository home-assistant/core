"""The S3 integration."""

from __future__ import annotations

import logging
from typing import cast

from aiobotocore.client import AioBaseClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ._api import get_client
from .const import DATA_BACKUP_AGENT_LISTENERS

type S3ConfigEntry = ConfigEntry[AioBaseClient]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: S3ConfigEntry) -> bool:
    """Set up S3 from a config entry."""

    client = await get_client(cast(dict, entry.data)).__aenter__()
    entry.runtime_data = client

    # Notify backup listeners
    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: S3ConfigEntry) -> bool:
    """Unload a config entry."""
    client = entry.runtime_data
    await client.__aexit__(None, None, None)
    return True
