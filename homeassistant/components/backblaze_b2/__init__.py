"""The Backblaze integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from b2sdk.v2 import B2Api, Bucket, InMemoryAccountInfo, exception

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

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
    """Set up Backblaze from a config entry."""

    info = InMemoryAccountInfo()
    b2_api = B2Api(info)

    def _authorize_and_get_bucket_sync() -> Bucket:
        """Synchronously authorize the Backblaze account and retrieve the bucket.

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
        _LOGGER.error(
            "Backblaze authentication failed for key ID '%s': %s",
            entry.data[CONF_KEY_ID],
            err,
        )
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except exception.RestrictedBucket as err:
        _LOGGER.error(
            "Access to Backblaze bucket '%s' is restricted for key ID '%s': %s",
            entry.data[CONF_BUCKET],
            entry.data[CONF_KEY_ID],
            err,
        )
        create_bucket_access_restricted_issue(hass, entry, err.bucket_name)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="restricted_bucket",
            translation_placeholders={
                "restricted_bucket_name": err.bucket_name,
            },
        ) from err
    except exception.NonExistentBucket as err:
        _LOGGER.error(
            "Backblaze bucket '%s' does not exist for key ID '%s': %s",
            entry.data[CONF_BUCKET],
            entry.data[CONF_KEY_ID],
            err,
        )
        create_bucket_not_found_issue(hass, entry, entry.data[CONF_BUCKET])
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="invalid_bucket_name",
        ) from err
    except exception.ConnectionReset as err:
        _LOGGER.error("Failed to connect to Backblaze. Connection reset: %s", err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except exception.MissingAccountData as err:
        _LOGGER.error(
            "Missing account data during Backblaze authorization for key ID '%s': %s",
            entry.data[CONF_KEY_ID],
            err,
        )
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except Exception as err:
        _LOGGER.exception(
            "An unexpected error occurred during Backblaze setup for key ID '%s'",
            entry.data[CONF_KEY_ID],
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unknown_error",
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
        del _now  # Required by async_track_time_interval interface
        await async_check_for_repair_issues(hass, entry)

    entry.async_on_unload(
        async_track_time_interval(hass, _periodic_issue_check, timedelta(minutes=30))
    )

    hass.async_create_task(async_check_for_repair_issues(hass, entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Unload a Backblaze config entry.

    Any resources directly managed by this entry that need explicit shutdown
    would be handled here. In this case, the `async_on_state_change` listener
    handles the notification logic on unload.
    """
    del hass, entry  # Required by interface but not used
    return True
