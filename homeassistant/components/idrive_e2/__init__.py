"""The IDrive e2 integration."""

from __future__ import annotations

import logging
from typing import cast

import boto3
from botocore.exceptions import ClientError, ConnectionError, ParamValidationError

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

type IDriveE2ConfigEntry = ConfigEntry[boto3.client]


_LOGGER = logging.getLogger(__name__)


def _initialize_client(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
) -> boto3.client:
    """Fully initialize boto3 S3 client."""

    # NOTE: We use boto3 instead of aiobotocore.AioSession because AioSession
    # causes blocking operations inside the event loop.
    # Two examples include:
    # - os.listdir
    # - ssl.SSLContext.load_verify_locations
    # These lead to 'Detected blocking call` warnings. Using boto3 inside
    # async_add_executor_job avoids these issues by running blocking code off the event loop.
    session = boto3.session.Session()
    client = session.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    client.head_bucket(Bucket=bucket)

    return client


async def async_setup_entry(hass: HomeAssistant, entry: IDriveE2ConfigEntry) -> bool:
    """Set up IDrive e2 from a config entry."""

    data = cast(dict, entry.data)
    try:
        client = await hass.async_add_executor_job(
            _initialize_client,
            data[CONF_ENDPOINT_URL],
            data[CONF_ACCESS_KEY_ID],
            data[CONF_SECRET_ACCESS_KEY],
            data[CONF_BUCKET],
        )
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
    except ConnectionError as err:
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
    client: boto3.client = entry.runtime_data
    await hass.async_add_executor_job(client.close)
    return True
