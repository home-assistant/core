"""The qbittorrent component."""
import logging

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

from .client import create_client
from .const import DATA_KEY_CLIENT, DATA_KEY_NAME, DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Qbittorrent component."""
    # Make sure coordinator is initialized.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Qbittorrent from a config entry."""
    name = "Qbittorrent"
    try:
        client = await hass.async_add_executor_job(
            create_client,
            entry.data[CONF_URL],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )
    except LoginRequired:
        _LOGGER.error("Invalid authentication")
        return
    except RequestException as err:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady from err

    hass.data[DOMAIN][entry.data[CONF_URL]] = {
        DATA_KEY_CLIENT: client,
        DATA_KEY_NAME: name,
    }
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True
