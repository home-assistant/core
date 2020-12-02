"""The qbittorrent component."""
import logging

from qbittorrent.client import Client
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_KEY_CLIENT,
    DATA_KEY_COORDINATOR,
    DATA_KEY_NAME,
    DOMAIN,
    SCAN_INTERVAL,
)
from .services import async_setup_services
from .wrapper_functions import create_client, get_main_data_client

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Qbittorrent component."""
    # Make sure coordinator is initialized.
    hass.data.setdefault(DOMAIN, {})
    await async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Qbittorrent from a config entry."""
    name = "Qbittorrent"

    configtest = await hass.async_add_executor_job(
        create_client,
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    if type(configtest) is not Client:
        return

    client = configtest

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            await hass.async_add_executor_job(get_main_data_client, client)

        except RequestException as err:
            raise UpdateFailed(f"Failed to communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )
    hass.data[DOMAIN][entry.data[CONF_URL]] = {
        DATA_KEY_CLIENT: client,
        DATA_KEY_COORDINATOR: coordinator,
        DATA_KEY_NAME: name,
    }
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True
