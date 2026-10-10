"""Coordinator file that handles data updates for Solyx Energy device entities."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from solyx_energy_api.exceptions import (
    SolyxEnergyAuthError,
    SolyxEnergyDataError,
    SolyxEnergyTokenError,
)

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTRIBUTE_BOILER_CURRENT,
    ATTRIBUTE_BOILER_POWER,
    ATTRIBUTE_BOILER_VOLTAGE,
    ATTRIBUTE_DAYS_SINCE_MAX_TEMPERATURE,
    ATTRIBUTE_GRID_POWER,
    ATTRIBUTE_LEGIONELLA_DAYS,
    ATTRIBUTE_SAVED_THIS_MONTH,
    ATTRIBUTE_SAVED_THIS_WEEK,
    ATTRIBUTE_SAVED_TODAY,
    DATA_INTERVAL_SECONDS,
    DOMAIN,
)
from .util import parse_float

if TYPE_CHECKING:
    from solyx_energy_api.client import SolyxEnergyApiClient

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SolyxEnergyData:
    """Hold a snapshot of all Solyx Energy integration values exposed to Home Assistant."""

    boiler_current: float | None
    boiler_power: float | None
    boiler_voltage: float | None
    days_since_maximum_temperature: float | None
    grid_power: float | None
    legionella_days: float | None
    saved_this_month: float | None
    saved_this_week: float | None
    saved_today: float | None


class SolyxEnergyCoordinator(DataUpdateCoordinator[SolyxEnergyData]):
    """Coordinator that fetches data over HTTPS using the SolyxEnergyApiClient class."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: SolyxEnergyApiClient,
        device_id: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the main coordinator for the Solyx Energy integration."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DATA_INTERVAL_SECONDS),
        )
        self.api_client = api_client
        self.device_id = device_id

    @override
    async def _async_update_data(self) -> SolyxEnergyData:
        """Fetch data with the SolyxEnergyApiClient class and update the device entities accordingly."""
        try:
            _LOGGER.debug("Retrieving data from Solyx Energy API")
            nymo_data = await self.api_client.async_get_asset_data(self.device_id)
        except SolyxEnergyAuthError as err:
            raise UpdateFailed(f"Auth error: {err}") from err
        except (SolyxEnergyTokenError, SolyxEnergyDataError) as err:
            raise UpdateFailed(f"API error: {err}") from err

        return SolyxEnergyData(
            boiler_current=parse_float(nymo_data, ATTRIBUTE_BOILER_CURRENT),
            boiler_power=parse_float(nymo_data, ATTRIBUTE_BOILER_POWER),
            boiler_voltage=parse_float(nymo_data, ATTRIBUTE_BOILER_VOLTAGE),
            days_since_maximum_temperature=parse_float(
                nymo_data, ATTRIBUTE_DAYS_SINCE_MAX_TEMPERATURE
            ),
            grid_power=parse_float(nymo_data, ATTRIBUTE_GRID_POWER),
            legionella_days=parse_float(nymo_data, ATTRIBUTE_LEGIONELLA_DAYS),
            saved_this_month=parse_float(nymo_data, ATTRIBUTE_SAVED_THIS_MONTH),
            saved_this_week=parse_float(nymo_data, ATTRIBUTE_SAVED_THIS_WEEK),
            saved_today=parse_float(nymo_data, ATTRIBUTE_SAVED_TODAY),
        )
