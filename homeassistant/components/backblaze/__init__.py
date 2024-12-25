"""Integration for Backblaze B2 Cloud Storage."""

from __future__ import annotations

from dataclasses import dataclass

from b2sdk.v2 import AuthInfoCache, B2Api, Bucket, InMemoryAccountInfo
from b2sdk.v2.exception import InvalidAuthToken, NonExistentBucket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    CONF_APPLICATION_KEY,
    CONF_APPLICATION_KEY_ID,
    CONF_BUCKET,
    DATA_BACKUP_AGENT_LISTENERS,
)

type BackblazeConfigEntry = ConfigEntry[BackblazeonfigEntryData]


@dataclass(kw_only=True)
class BackblazeonfigEntryData:
    """Dataclass holding all config entry data for a Backblaze entry."""

    api: B2Api
    bucket: Bucket


async def async_setup_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Set up Backblaze from a config entry."""

    info = InMemoryAccountInfo()
    backblaze = B2Api(info, cache=AuthInfoCache(info))
    try:
        await hass.async_add_executor_job(
            backblaze.authorize_account,
            "production",
            entry.data[CONF_APPLICATION_KEY_ID],
            entry.data[CONF_APPLICATION_KEY],
        )
        bucket = await hass.async_add_executor_job(
            backblaze.get_bucket_by_id, entry.data[CONF_BUCKET]
        )
    except InvalidAuthToken as err:
        raise ConfigEntryAuthFailed(
            f"Invalid authentication token for Backblaze account: {err}"
        ) from err
    except NonExistentBucket as err:
        raise ConfigEntryNotReady(
            f"Non-existent bucket for Backblaze account: {err}"
        ) from err

    entry.runtime_data = BackblazeonfigEntryData(api=backblaze, bucket=bucket)

    # Notify backup listeners
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Unload Backblaze config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
