"""The flume integration."""
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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    BASE_TOKEN_FILENAME,
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    PLATFORMS,
)


def _setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Config entry set up in executor."""
    config = entry.data

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    flume_token_full_path = hass.config.path(f"{BASE_TOKEN_FILENAME}-{username}")

    http_session = Session()

    try:
        flume_auth = FlumeAuth(
            username,
            password,
            client_id,
            client_secret,
            flume_token_file=flume_token_full_path,
            http_session=http_session,
        )
        flume_devices = FlumeDeviceList(flume_auth, http_session=http_session)
    except RequestException as ex:
        raise ConfigEntryNotReady from ex
    except Exception as ex:
        raise ConfigEntryAuthFailed from ex

    return flume_auth, flume_devices, http_session


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up flume from a config entry."""

    flume_auth, flume_devices, http_session = await hass.async_add_executor_job(
        _setup_entry, hass, entry
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        FLUME_DEVICES: flume_devices,
        FLUME_AUTH: flume_auth,
        FLUME_HTTP_SESSION: http_session,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][FLUME_HTTP_SESSION].close()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
