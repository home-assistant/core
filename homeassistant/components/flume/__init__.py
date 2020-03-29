"""The flume integration."""
import asyncio
from functools import partial
import logging

from pyflume import FlumeDeviceList
from requests import Session
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    BASE_TOKEN_FILENAME,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_TOKEN_FULL_PATH,
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
        flume_devices = await hass.async_add_executor_job(
            partial(
                FlumeDeviceList,
                username,
                password,
                client_id,
                client_secret,
                flume_token_full_path,
                http_session=http_session,
            )
        )
    except RequestException:
        raise ConfigEntryNotReady
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("Invalid credentials for flume: %s", ex)
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        FLUME_DEVICES: flume_devices,
        FLUME_TOKEN_FULL_PATH: flume_token_full_path,
        FLUME_HTTP_SESSION: http_session,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
