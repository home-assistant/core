"""The flume integration."""
import asyncio
from functools import partial
import logging

from pyflume import FlumeAuth, FlumeDeviceList
from requests import Session
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    BASE_TOKEN_FILENAME,
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the flume component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up flume from a config entry."""

    config = entry.data

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    flume_token_full_path = hass.config.path(f"{BASE_TOKEN_FILENAME}-{username}")

    http_session = Session()

    try:
        flume_auth = await hass.async_add_executor_job(
            partial(
                FlumeAuth,
                username,
                password,
                client_id,
                client_secret,
                flume_token_file=flume_token_full_path,
                http_session=http_session,
            )
        )
        flume_devices = await hass.async_add_executor_job(
            partial(
                FlumeDeviceList,
                flume_auth,
                http_session=http_session,
            )
        )
    except RequestException as ex:
        raise ConfigEntryNotReady from ex
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("Invalid credentials for flume: %s", ex)
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        FLUME_DEVICES: flume_devices,
        FLUME_AUTH: flume_auth,
        FLUME_HTTP_SESSION: http_session,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][entry.entry_id][FLUME_HTTP_SESSION].close()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
