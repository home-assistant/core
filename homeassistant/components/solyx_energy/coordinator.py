"""Coordinator file that handles data updates for Solyx Energy device entities."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, override

from solyx_energy_api.exceptions import (
    SolyxEnergyAuthError,
    SolyxEnergyDataError,
    SolyxEnergyTokenError,
)

from homeassistant.exceptions import ConfigEntryAuthFailed
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
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SolyxEnergyData:
    """Hold a snapshot of all Solyx Energy integration values, using the internal Solyx platform name."""

    boilerCurrent: float | None  # noqa: N815
    boilerPower: float | None  # noqa: N815
    boilerVoltage: float | None  # noqa: N815
    daysSinceMaximumTemperature: float | None  # noqa: N815
    gridPower: float | None  # noqa: N815
    legionellaDays: float | None  # noqa: N815
    savedThisMonth: float | None  # noqa: N815
    savedThisWeek: float | None  # noqa: N815
    savedToday: float | None  # noqa: N815


class SolyxEnergyCoordinator(DataUpdateCoordinator[SolyxEnergyData]):
    """Coordinator that fetches and sends data over HTTPS using the SolyxEnergyApiClient class."""

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
        self._settle_unsub: CALLBACK_TYPE | None = None
        if self.config_entry is not None:
            self.config_entry.async_on_unload(self._async_cancel_settle_timer)

    @override
    async def _async_update_data(self) -> SolyxEnergyData:
        """Fetch data with the SolyxEnergyApiClient class and update the device entities accordingly."""
        try:
            _LOGGER.debug("Retrieving data from Solyx Energy API")
            nymo_data = await self.api_client.async_get_asset_data(self.device_id)
        except SolyxEnergyAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (SolyxEnergyTokenError, SolyxEnergyDataError) as err:
            raise UpdateFailed(f"API error: {err}") from err

        return SolyxEnergyData(
            boilerCurrent=parse_float(nymo_data, ATTRIBUTE_BOILER_CURRENT),
            boilerPower=parse_float(nymo_data, ATTRIBUTE_BOILER_POWER),
            boilerVoltage=parse_float(nymo_data, ATTRIBUTE_BOILER_VOLTAGE),
            daysSinceMaximumTemperature=parse_float(
                nymo_data, ATTRIBUTE_DAYS_SINCE_MAX_TEMPERATURE
            ),
            gridPower=parse_float(nymo_data, ATTRIBUTE_GRID_POWER),
            legionellaDays=parse_float(nymo_data, ATTRIBUTE_LEGIONELLA_DAYS),
            savedThisMonth=parse_float(nymo_data, ATTRIBUTE_SAVED_THIS_MONTH),
            savedThisWeek=parse_float(nymo_data, ATTRIBUTE_SAVED_THIS_WEEK),
            savedToday=parse_float(nymo_data, ATTRIBUTE_SAVED_TODAY),
        )

    async def _async_settle_refresh(self, _now: datetime) -> None:
        """Refresh data after a write has settled on the Solyx cloud platform."""
        self._settle_unsub = None
        await self.async_request_refresh()

    def _async_cancel_settle_timer(self) -> None:
        """Cancel any pending settle timer when the config entry is unloaded."""
        if self._settle_unsub is not None:
            self._settle_unsub()
            self._settle_unsub = None
