"""The totalconnect component."""

from datetime import timedelta
import logging

from total_connect_client.client import TotalConnectClient
from total_connect_client.exceptions import AuthenticationError, TotalConnectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_USERCODES, DOMAIN

PLATFORMS = ["alarm_control_panel", "binary_sensor"]

CONFIG_SCHEMA = cv.deprecated(DOMAIN)
SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up upon config entry in user interface."""
    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    if CONF_USERCODES not in conf:
        # should only happen for those who used UI before we added usercodes
        raise ConfigEntryAuthFailed("No usercodes in TotalConnect configuration")

    temp_codes = conf[CONF_USERCODES]
    usercodes = {int(code): temp_codes[code] for code in temp_codes}

    try:
        client = await hass.async_add_executor_job(
            TotalConnectClient, username, password, usercodes
        )
    except AuthenticationError as exception:
        raise ConfigEntryAuthFailed("TotalConnect authentication failed") from exception

    coordinator = TotalConnectDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class TotalConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to fetch data from TotalConnect."""

    def __init__(self, hass: HomeAssistant, client):
        """Initialize."""
        self.hass = hass
        self.client = client
        super().__init__(
            hass, logger=_LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL
        )

    async def _async_update_data(self):
        """Update data."""
        await self.hass.async_add_executor_job(self.sync_update_data)

    def sync_update_data(self):
        """Fetch synchronous data from TotalConnect."""
        try:
            for location_id in self.client.locations:
                self.client.locations[location_id].get_panel_meta_data()
        except AuthenticationError as exception:
            # should only encounter if password changes during operation
            raise ConfigEntryAuthFailed(
                "TotalConnect authentication failed"
            ) from exception
        except TotalConnectError as exception:
            raise UpdateFailed(exception) from exception
        except ValueError as exception:
            raise UpdateFailed("Unknown state from TotalConnect") from exception
