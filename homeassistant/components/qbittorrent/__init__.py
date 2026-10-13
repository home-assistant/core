"""The qbittorrent component."""

import logging

from qbittorrentapi import APIConnectionError, Forbidden403Error, LoginFailed

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import QBittorrentConfigEntry, QBittorrentDataCoordinator
from .helpers import setup_client
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

CONF_ENTRY = "entry"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up qBittorrent services."""

    async_setup_services(hass)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: QBittorrentConfigEntry
) -> bool:
    """Set up qBittorrent from a config entry."""

    try:
        client = await hass.async_add_executor_job(
            setup_client,
            config_entry.data[CONF_URL],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_VERIFY_SSL],
        )
    except LoginFailed as err:
        raise ConfigEntryNotReady("Invalid credentials") from err
    except Forbidden403Error as err:
        raise ConfigEntryNotReady("Fail to log in, banned user ?") from err
    except APIConnectionError as exc:
        raise ConfigEntryNotReady("Fail to connect to qBittorrent") from exc

    coordinator = QBittorrentDataCoordinator(hass, config_entry, client)

    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: QBittorrentConfigEntry
) -> bool:
    """Unload qBittorrent config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
