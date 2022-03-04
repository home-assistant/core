"""The Airzone integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioairzone.common import ConnectionOptions
from aioairzone.localapi_device import AirzoneLocalApi
from aiohttp.client_exceptions import ClientConnectorError
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AIOAIRZONE_DEVICE_TIMEOUT_SEC, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Airzone from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )

    airzone = AirzoneLocalApi(aiohttp_client.async_get_clientsession(hass), options)

    await airzone.update_airzone()

    coordinator = AirzoneUpdateCoordinator(hass, airzone)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AirzoneUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Airzone device."""

    def __init__(self, hass: HomeAssistant, airzone: AirzoneLocalApi) -> None:
        """Initialize."""
        self.airzone = airzone
        self.update_checked = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Update data via library."""
        async with async_timeout.timeout(AIOAIRZONE_DEVICE_TIMEOUT_SEC):
            try:
                await self.airzone.update_airzone()
                return self.airzone.data()
            except ClientConnectorError as error:
                raise UpdateFailed(error) from error
