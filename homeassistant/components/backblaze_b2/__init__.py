"""The Backblaze B2 integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from b2sdk.v2 import Bucket, exception

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

# Import from b2_client to ensure timeout configuration is applied
from .b2_client import B2Api, InMemoryAccountInfo
from .const import (
    BACKBLAZE_REALM,
    CONF_APPLICATION_KEY,
    CONF_BUCKET,
    CONF_KEY_ID,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from .repairs import (
    async_check_for_repair_issues,
    create_bucket_access_restricted_issue,
    create_bucket_not_found_issue,
)

_LOGGER = logging.getLogger(__name__)

type BackblazeConfigEntry = ConfigEntry[Bucket]


async def async_setup_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Set up Backblaze B2 from a config entry."""

    info = InMemoryAccountInfo()
    b2_api = B2Api(info)

    def _authorize_and_get_bucket_sync() -> Bucket:
        """Synchronously authorize the Backblaze B2 account and retrieve the bucket.

        This function runs in the event loop's executor as b2sdk operations are blocking.
        """
        b2_api.authorize_account(
            BACKBLAZE_REALM,
            entry.data[CONF_KEY_ID],
            entry.data[CONF_APPLICATION_KEY],
        )
        return b2_api.get_bucket_by_name(entry.data[CONF_BUCKET])

    try:
        bucket = await hass.async_add_executor_job(_authorize_and_get_bucket_sync)
    except exception.Unauthorized as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except exception.RestrictedBucket as err:
        create_bucket_access_restricted_issue(hass, entry, err.bucket_name)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="restricted_bucket",
            translation_placeholders={
                "restricted_bucket_name": err.bucket_name,
            },
        ) from err
    except exception.NonExistentBucket as err:
        create_bucket_not_found_issue(hass, entry, entry.data[CONF_BUCKET])
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="invalid_bucket_name",
        ) from err
    except (
        exception.B2ConnectionError,
        exception.B2RequestTimeout,
        exception.ConnectionReset,
    ) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except exception.MissingAccountData as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err

    entry.runtime_data = bucket

    def _async_notify_backup_listeners() -> None:
        """Notify any registered backup agent listeners."""
        _LOGGER.debug("Notifying backup listeners for entry %s", entry.entry_id)
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(_async_notify_backup_listeners))

    async def _periodic_issue_check(_now: Any) -> None:
        """Periodically check for repair issues."""
        await async_check_for_repair_issues(hass, entry)

    entry.async_on_unload(
        async_track_time_interval(hass, _periodic_issue_check, timedelta(minutes=30))
    )

    hass.async_create_task(async_check_for_repair_issues(hass, entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Unload a Backblaze B2 config entry.

    Any resources directly managed by this entry that need explicit shutdown
    would be handled here. In this case, the `async_on_state_change` listener
    handles the notification logic on unload.
    """
    return True
