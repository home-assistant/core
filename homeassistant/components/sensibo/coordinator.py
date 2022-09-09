"""DataUpdateCoordinator for the Sensibo integration."""
from __future__ import annotations

from datetime import timedelta

from pysensibo import SensiboClient
from pysensibo.exceptions import AuthenticationError, SensiboError
from pysensibo.model import SensiboData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT

REQUEST_REFRESH_DELAY = 0.35


class SensiboDataUpdateCoordinator(DataUpdateCoordinator):
    """A Sensibo Data Update Coordinator."""

    data: SensiboData

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Sensibo coordinator."""
        self.client = SensiboClient(
            entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
            timeout=TIMEOUT,
        )
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> SensiboData:
        """Fetch data from Sensibo."""

        try:
            data = await self.client.async_get_devices_data()
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed from error
        except SensiboError as error:
            raise UpdateFailed from error

        if not data.raw:
            raise UpdateFailed("No devices found")
        return data
