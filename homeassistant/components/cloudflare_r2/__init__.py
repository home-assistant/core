"""The Cloudflare R2 integration."""

from __future__ import annotations

import logging
from typing import cast

from aiobotocore.client import AioBaseClient as S3Client
from aiobotocore.session import AioSession
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ParamValidationError,
)

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

type R2ConfigEntry = ConfigEntry[S3Client]


_LOGGER = logging.getLogger(__name__)


S3_API_VERSION = "2006-03-01"


def _preload_botocore_data(session: AioSession) -> None:
    """Pre-load botocore S3 data to avoid blocking the event loop.

    botocore performs synchronous file I/O (os.listdir, gzip.open) when loading
    service model data during client creation. Pre-loading the data into the
    session's internal loader cache avoids these blocking calls.
    """
    loader = session.get_component("data_loader")
    loader.load_service_model("s3", "service-2", S3_API_VERSION)
    loader.load_service_model("s3", "endpoint-rule-set-1", S3_API_VERSION)
    loader.load_data("partitions")
    loader.load_data("sdk-default-configuration")


async def async_setup_entry(hass: HomeAssistant, entry: R2ConfigEntry) -> bool:
    """Set up Cloudflare R2 from a config entry."""

    data = cast(dict, entry.data)
    session = AioSession()
    await hass.async_add_executor_job(_preload_botocore_data, session)

    try:
        # pylint: disable-next=unnecessary-dunder-call
        client = await session.create_client(
            "s3",
            endpoint_url=data.get(CONF_ENDPOINT_URL),
            aws_secret_access_key=data[CONF_SECRET_ACCESS_KEY],
            aws_access_key_id=data[CONF_ACCESS_KEY_ID],
            api_version=S3_API_VERSION,
        ).__aenter__()
        await client.head_bucket(Bucket=data[CONF_BUCKET])
    except ClientError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from err
    except ParamValidationError as err:
        if "Invalid bucket name" in str(err):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_bucket_name",
            ) from err
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
