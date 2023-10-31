"""DataUpdateCoordinator for the co2signal integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioelectricitymaps import ElectricityMaps
from aioelectricitymaps.exceptions import ElectricityMapsError, InvalidToken
from aioelectricitymaps.models import CarbonIntensityResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COUNTRY_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CO2SignalCoordinator(DataUpdateCoordinator[CarbonIntensityResponse]):
    """Data update coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: ElectricityMaps) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=15)
        )
        self.client = client

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self.config_entry.entry_id

    async def _async_update_data(self) -> CarbonIntensityResponse:
        """Fetch the latest data from the source."""

        async with self.client as em:
            try:
                if CONF_COUNTRY_CODE in self.config_entry.data:
                    return await em.latest_carbon_intensity_by_country_code(
                        code=self.config_entry.data[CONF_COUNTRY_CODE]
                    )

                return await em.latest_carbon_intensity_by_coordinates(
                    lat=self.config_entry.data.get(
                        CONF_LATITUDE, self.hass.config.latitude
                    ),
                    lon=self.config_entry.data.get(
                        CONF_LONGITUDE, self.hass.config.longitude
                    ),
                )
            except InvalidToken as err:
                raise ConfigEntryError from err
            except ElectricityMapsError as err:
                raise UpdateFailed(str(err)) from err
