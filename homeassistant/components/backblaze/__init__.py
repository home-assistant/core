"""The Backblaze integration."""

from __future__ import annotations

from typing import cast

from b2sdk.v2 import B2Api, Bucket, InMemoryAccountInfo, exception

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import (
    CONF_APPLICATION_KEY,
    CONF_BUCKET,
    CONF_KEY_ID,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)

type BackblazeConfigEntry = ConfigEntry[Bucket]


async def async_setup_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Set up Backblaze from a config entry."""

    info = InMemoryAccountInfo()
    b2_api = B2Api(info)

    data = cast(dict, entry.data)

    try:

        def _authorize_and_get_bucket() -> Bucket:
            b2_api.authorize_account(
                "production",
                data[CONF_KEY_ID],
                data[CONF_APPLICATION_KEY],
            )
            return b2_api.get_bucket_by_name(data[CONF_BUCKET])

        bucket = await hass.async_add_executor_job(_authorize_and_get_bucket)

    except exception.Unauthorized as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except exception.RestrictedBucket as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="restricted_bucket",
            translation_placeholders={
                "restricted_bucket_name": err.bucket_name,
            },
        ) from err
    except exception.NonExistentBucket as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_bucket_name",
        ) from err
    except exception.ConnectionReset as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except exception.MissingAccountData as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err

    entry.runtime_data = bucket

    def _async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(_async_notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Unload a config entry."""
    return True
