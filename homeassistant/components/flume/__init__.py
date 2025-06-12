"""The flume integration."""

from __future__ import annotations

from pyflume import FlumeAuth, FlumeDeviceList
from requests import Session
from requests.exceptions import RequestException

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import BASE_TOKEN_FILENAME, DOMAIN, PLATFORMS
from .coordinator import (
    FlumeConfigEntry,
    FlumeNotificationDataUpdateCoordinator,
    FlumeRuntimeData,
)
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration."""
    async_setup_services(hass)
    return True


def _setup_entry(
    hass: HomeAssistant, entry: FlumeConfigEntry
) -> tuple[FlumeAuth, FlumeDeviceList, Session]:
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


async def async_setup_entry(hass: HomeAssistant, entry: FlumeConfigEntry) -> bool:
    """Set up flume from a config entry."""

    flume_auth, flume_devices, http_session = await hass.async_add_executor_job(
        _setup_entry, hass, entry
    )
    notification_coordinator = FlumeNotificationDataUpdateCoordinator(
        hass=hass, config_entry=entry, auth=flume_auth
    )

    entry.runtime_data = FlumeRuntimeData(
        devices=flume_devices,
        auth=flume_auth,
        http_session=http_session,
        notifications_coordinator=notification_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlumeConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.http_session.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
