"""The IDrive e2 integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from aiobotocore.client import AioBaseClient as S3Client
from aiobotocore.session import AioSession
from aiohttp import ClientError as AiohttpClientError
from botocore.exceptions import ClientError, ConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)

type IDriveE2ConfigEntry = ConfigEntry[S3Client]


_LOGGER = logging.getLogger(__name__)


async def _async_safe_client_close(client: S3Client | None) -> None:
    """Close client without masking the original exception."""
    if client is None:
        return
    try:
        # Best effort to close the client which doesn't mask the setup exception
        await client.close()
    except AiohttpClientError, OSError, RuntimeError:
        _LOGGER.debug("Failed to close aiobotocore client", exc_info=True)


async def async_setup_entry(hass: HomeAssistant, entry: IDriveE2ConfigEntry) -> bool:
    """Set up IDrive e2 from a config entry."""

    session = AioSession()
    client: S3Client | None = None
    try:
        # pylint: disable-next=unnecessary-dunder-call
        client = await session.create_client(
            "s3",
            endpoint_url=entry.data[CONF_ENDPOINT_URL],
            aws_secret_access_key=entry.data[CONF_SECRET_ACCESS_KEY],
            aws_access_key_id=entry.data[CONF_ACCESS_KEY_ID],
        ).__aenter__()
        await cast(Any, client).head_bucket(Bucket=entry.data[CONF_BUCKET])
    except ClientError as err:
        await _async_safe_client_close(client)
        code = str(err.response.get("Error", {}).get("Code", ""))
        if code in ("404", "NoSuchBucket"):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="bucket_not_found",
                translation_placeholders={"bucket": entry.data[CONF_BUCKET]},
            ) from err

        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except ValueError as err:
        await _async_safe_client_close(client)
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_endpoint_url",
        ) from err
    except ConnectionError as err:
        await _async_safe_client_close(client)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    entry.runtime_data = client

    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IDriveE2ConfigEntry) -> bool:
    """Unload a config entry."""
    client = entry.runtime_data
    await client.close()
    return True
