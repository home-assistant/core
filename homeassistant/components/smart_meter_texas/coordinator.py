"""DataUpdateCoordinator for the Smart Meter Texas integration."""

import logging

from smart_meter_texas import Account, Client, Meter
from smart_meter_texas.exceptions import (
    SmartMeterTexasAPIError,
    SmartMeterTexasAuthError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.ssl import get_default_context

from .const import DEBOUNCE_COOLDOWN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SmartMeterTexasData:
    """Manages coordination of API data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        account: Account,
    ) -> None:
        """Initialize the data coordinator."""
        self.account = account
        self.client = Client(
            aiohttp_client.async_get_clientsession(hass),
            account,
            ssl_context=get_default_context(),
        )
        self.meters: list[Meter] = []

    async def setup(self) -> None:
        """Fetch all of the user's meters."""
        self.meters = await self.account.fetch_meters(self.client)
        _LOGGER.debug("Discovered %s meter(s)", len(self.meters))

    async def read_meters(self) -> list[Meter]:
        """Read each meter."""
        for meter in self.meters:
            try:
                await meter.read_meter(self.client)
            except (SmartMeterTexasAPIError, SmartMeterTexasAuthError) as error:
                raise UpdateFailed(error) from error
        return self.meters


class SmartMeterTexasCoordinator(DataUpdateCoordinator[SmartMeterTexasData]):
    """Class to manage fetching Smart Meter Texas data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        smart_meter_texas_data: SmartMeterTexasData,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Smart Meter Texas",
            update_interval=SCAN_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=DEBOUNCE_COOLDOWN, immediate=True
            ),
        )
        self._smart_meter_texas_data = smart_meter_texas_data

    async def _async_update_data(self) -> SmartMeterTexasData:
        """Fetch latest data."""
        _LOGGER.debug("Fetching latest data")
        await self._smart_meter_texas_data.read_meters()
        return self._smart_meter_texas_data
