"""The Risco integration."""
import asyncio
from datetime import timedelta
import logging

from pyrisco import CannotConnectError, OperationError, RiscoAPI, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_COORDINATOR, DOMAIN, NUM_RETRIES

PLATFORMS = ["alarm_control_panel"]


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Risco component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Risco from a config entry."""
    data = entry.data
    risco = RiscoAPI(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PIN])
    try:
        await risco.login(async_get_clientsession(hass))
    except (CannotConnectError, UnauthorizedError) as error:
        raise ConfigEntryNotReady() from error

    coordinator = RiscoDataUpdateCoordinator(hass, risco)
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
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


def call_with_retry(func):
    """Make a call to the Risco API and retry if session expires.

    The risco api ends the session every hour.
    The only way around it is retrying here.
    For some odd reason, retrying in the package doesn't work...
    """

    async def _wrap(*args, **kwargs):
        for i in range(NUM_RETRIES):
            try:
                return await func(*args, **kwargs)
            except UnauthorizedError:
                _LOGGER.info("Risco session. Expired. Retry %d", i + 1)
                await args[0].risco.close()
                await args[0].risco.login()
                if i + 1 == NUM_RETRIES:
                    raise

    return _wrap


class RiscoDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching risco data."""

    def __init__(self, hass, risco):
        """Initialize global risco data updater."""
        self.risco = risco
        interval = timedelta(seconds=30)
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=interval,
        )

    @call_with_retry
    async def _get_state(self):
        return await self.risco.get_state()

    async def _async_update_data(self):
        """Fetch data from risco."""
        try:
            return await self._get_state()
        except (CannotConnectError, UnauthorizedError, OperationError) as error:
            raise UpdateFailed from error
