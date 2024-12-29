"""Integration for S3 Cloud Storage."""

from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    CONF_ACCESS_KEY,
    CONF_BUCKET,
    CONF_S3_URL,
    CONF_SECRET_KEY,
    DATA_BACKUP_AGENT_LISTENERS,
    LOGGER,
)

type S3ConfigEntry = ConfigEntry["S3ConfigEntryData"]


@dataclass(kw_only=True)
class S3ConfigEntryData:
    """Dataclass holding all config entry data for a S3 entry."""

    bucket: str
    client: boto3.session.Session.client


async def async_setup_entry(hass: HomeAssistant, entry: S3ConfigEntry) -> bool:
    """Set up S3 from a config entry."""
    LOGGER.info("Entry details: %s", entry)
    # Create a session using your credentials
    session = boto3.Session(
        aws_access_key_id=entry.data[CONF_ACCESS_KEY],
        aws_secret_access_key=entry.data[CONF_SECRET_KEY],
    )

    try:
        # Create an S3 client
        client = await hass.async_add_executor_job(
            session.client,
            "s3",
            None,
            None,
            True,
            None,
            entry.data[CONF_S3_URL],
        )
        entry.runtime_data = S3ConfigEntryData(
            client=client, bucket=entry.data[CONF_BUCKET]
        )
    except ClientError as err:
        LOGGER.error("Error: %s", err)
        raise ConfigEntryAuthFailed(
            f"Invalid authentication token for S3 account: {err}"
        ) from err
    except Exception as err:  # noqa: BLE001
        LOGGER.error("Error: %s", err)
        raise ConfigEntryNotReady(f"Unknown err: {err}") from err

    # Notify backup listeners
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: S3ConfigEntry) -> bool:
    """Unload S3 config entry."""
    LOGGER.info("Unloading S3 config entry")
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    LOGGER.info("Notifying backup listeners")
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
