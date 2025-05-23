"""The Backblaze B2 integration."""

from __future__ import annotations

import logging
from typing import cast

from b2sdk.v2 import B2Api, Bucket, InMemoryAccountInfo, exception

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import (
    CONF_APPLICATION_KEY,
    CONF_BUCKET,
    CONF_KEY_ID,
    CONF_PREFIX,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)

type BackblazeConfigEntry = ConfigEntry[BackblazeConfig]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Set up Backblaze B2 from a config entry."""

    info = InMemoryAccountInfo()
    b2_api = B2Api(info)

    data = cast(dict, entry.data)
    prefix = data[CONF_PREFIX]

    try:
        _LOGGER.info(
            "Connecting to Backblaze B2 with application key id %s",
            data[CONF_KEY_ID],
        )
        await hass.async_add_executor_job(
            b2_api.authorize_account,
            "production",
            data[CONF_KEY_ID],
            data[CONF_APPLICATION_KEY],
        )

        bucket = await hass.async_add_executor_job(
            b2_api.get_bucket_by_name, data[CONF_BUCKET]
        )
        allowed = b2_api.account_info.get_allowed()

        # Check if capabilities contains 'writeFiles' and 'listFiles' and 'deleteFiles' and 'readFiles'
        if allowed is not None:
            if allowed is not None:
                capabilities = allowed["capabilities"]
                if not capabilities or not all(
                    capability in capabilities
                    for capability in (
                        "writeFiles",
                        "listFiles",
                        "deleteFiles",
                        "readFiles",
                    )
                ):
                    raise ConfigEntryError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_capability",
                    )

                allowed_prefix = cast(str, allowed.get("namePrefix", ""))
                if allowed_prefix and not prefix.startswith(allowed_prefix):
                    raise ConfigEntryError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_prefix",
                        translation_placeholders={
                            "allowed_prefix": allowed_prefix,
                        },
                    )

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

    if prefix and not prefix.endswith("/"):
        prefix += "/"

    entry.runtime_data = BackblazeConfig(bucket, prefix)

    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BackblazeConfigEntry) -> bool:
    """Unload a config entry."""
    return True


class BackblazeConfig:
    """Small wrapper for Backblaze configuration."""

    def __init__(self, bucket: Bucket, prefix: str) -> None:  # noqa: D107
        self.bucket = bucket
        self.prefix = prefix
