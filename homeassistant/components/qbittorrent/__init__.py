"""The qbittorrent component."""
import logging

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .helpers import setup_client

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up qBittorrent from a config entry."""
    assert entry.unique_id is not None
    try:
        await hass.async_add_executor_job(
            setup_client,
            entry.data[CONF_URL],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_VERIFY_SSL],
        )
    except LoginRequired as err:
        _LOGGER.error("Invalid credentials")
        raise ConfigEntryNotReady from err
    except RequestException as err:
        _LOGGER.error("Failed to connect")
        raise ConfigEntryNotReady from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
