"""The AWS S3 integration."""

from __future__ import annotations

import logging
from typing import cast

from aiobotocore.session import AioSession
from botocore.exceptions import ClientError, ConnectionError, ParamValidationError

from homeassistant.const import Platform
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
from .coordinator import S3ConfigEntry, S3DataUpdateCoordinator

_PLATFORMS = (Platform.SENSOR,)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: S3ConfigEntry) -> bool:
    """Set up S3 from a config entry."""

    data = cast(dict, entry.data)
    try:
        session = AioSession()
        # pylint: disable-next=unnecessary-dunder-call
        client = await session.create_client(
            "s3",
            endpoint_url=data.get(CONF_ENDPOINT_URL),
            aws_secret_access_key=data[CONF_SECRET_ACCESS_KEY],
            aws_access_key_id=data[CONF_ACCESS_KEY_ID],
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
    except ConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    coordinator = S3DataUpdateCoordinator(
        hass,
        entry=entry,
        client=client,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: S3ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if not unload_ok:
        return False
    coordinator = entry.runtime_data
    await coordinator.client.__aexit__(None, None, None)
    return True
