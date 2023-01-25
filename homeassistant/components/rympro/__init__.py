"""The Read Your Meter Pro integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyrympro import CannotConnectError, OperationError, RymPro, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = 60 * 60
PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Read Your Meter Pro from a config entry."""
    data = entry.data
    rympro = RymPro(async_get_clientsession(hass))
    rympro.set_token(data[CONF_TOKEN])
    try:
        await rympro.account_info()
    except CannotConnectError as error:
        raise ConfigEntryNotReady from error
    except UnauthorizedError:
        try:
            token = await rympro.login(data[CONF_EMAIL], data[CONF_PASSWORD], "ha")
            hass.config_entries.async_update_entry(
                entry,
                data={**data, CONF_TOKEN: token},
            )
        except UnauthorizedError as error:
            raise ConfigEntryAuthFailed from error

    coordinator = RymProDataUpdateCoordinator(hass, rympro, SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class RymProDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching RYM Pro data."""

    def __init__(self, hass: HomeAssistant, rympro: RymPro, scan_interval: int) -> None:
        """Initialize global RymPro data updater."""
        self.rympro = rympro
        interval = timedelta(seconds=scan_interval)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )

    async def _async_update_data(self):
        """Fetch data from Rym Pro."""
        try:
            return await self.rympro.last_read()
        except UnauthorizedError:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        except (CannotConnectError, OperationError) as error:
            raise UpdateFailed(error) from error
