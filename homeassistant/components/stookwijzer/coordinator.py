"""Class representing a Stookwijzer update coordinator."""

from datetime import timedelta

from stookwijzer import Stookwijzer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(minutes=60)

type StookwijzerConfigEntry = ConfigEntry[StookwijzerCoordinator]


class StookwijzerCoordinator(DataUpdateCoordinator[None]):
    """Stookwijzer update coordinator."""

    config_entry: StookwijzerConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: StookwijzerConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = Stookwijzer(
            async_get_clientsession(hass),
            config_entry.data[CONF_LATITUDE],
            config_entry.data[CONF_LONGITUDE],
        )

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.client.async_update()
        if self.client.advice is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data_received",
            )
