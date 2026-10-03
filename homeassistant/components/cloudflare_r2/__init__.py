"""The Cloudflare R2 integration."""

import logging
from typing import cast

from aiobotocore.client import AioBaseClient as S3Client
from aiobotocore.config import AioConfig
from aiobotocore.session import AioSession
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ParamValidationError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .const import (
    BUCKET_NOT_FOUND_ERROR_CODES,
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)

type R2ConfigEntry = ConfigEntry[S3Client]


_LOGGER = logging.getLogger(__name__)


async def _async_create_client(data: dict) -> S3Client:
    """Create an S3 client and verify the bucket is accessible."""
    session = AioSession()
    # pylint: disable-next=unnecessary-dunder-call
    client = await session.create_client(
        "s3",
        endpoint_url=data.get(CONF_ENDPOINT_URL),
        aws_secret_access_key=data[CONF_SECRET_ACCESS_KEY],
        aws_access_key_id=data[CONF_ACCESS_KEY_ID],
        config=AioConfig(warm_up_loader_caches=True),
    ).__aenter__()
    try:
        await client.head_bucket(Bucket=data[CONF_BUCKET])
    except Exception:
        await client.__aexit__(None, None, None)
        raise
    return client


async def async_setup_entry(hass: HomeAssistant, entry: R2ConfigEntry) -> bool:
    """Set up Cloudflare R2 from a config entry."""

    data = cast(dict, entry.data)
    try:
        client = await _async_create_client(data)
    except ClientError as err:
        if err.response["Error"]["Code"] in BUCKET_NOT_FOUND_ERROR_CODES:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="bucket_not_found",
                translation_placeholders={"bucket": data[CONF_BUCKET]},
            ) from err
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except ParamValidationError as err:
        if "Invalid bucket name" in str(err):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_bucket_name",
            ) from err
        raise
    except ValueError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_endpoint_url",
        ) from err
    except (ConnectionError, EndpointConnectionError) as err:
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


async def async_unload_entry(hass: HomeAssistant, entry: R2ConfigEntry) -> bool:
    """Unload a config entry."""
    client = entry.runtime_data
    await client.__aexit__(None, None, None)
    return True
