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
    ATTRIBUTE_BOILER_POWER,
    ATTRIBUTE_ENERGY_BOILER,
    ATTRIBUTE_GRID_POWER,
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

    boilerPower: float | None  # noqa: N815
    energyBoiler: float | None  # noqa: N815
    gridPower: float | None  # noqa: N815


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
            boilerPower=parse_float(nymo_data, ATTRIBUTE_BOILER_POWER),
            energyBoiler=parse_float(nymo_data, ATTRIBUTE_ENERGY_BOILER),
            gridPower=parse_float(nymo_data, ATTRIBUTE_GRID_POWER),
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
