"""The Read Your Meter Pro integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyrympro import CannotConnectError, OperationError, RymPro, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = 60 * 60

_LOGGER = logging.getLogger(__name__)


class RymProDataUpdateCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    """Class to manage fetching RYM Pro data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, rympro: RymPro
    ) -> None:
        """Initialize global RymPro data updater."""
        self.rympro = rympro
        interval = timedelta(seconds=SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=interval,
        )

    async def _async_update_data(self) -> dict[int, dict]:
        """Fetch data from Rym Pro."""
        try:
            meters = await self.rympro.last_read()
            for meter_id, meter in meters.items():
                meter["monthly_consumption"] = await self.rympro.monthly_consumption(
                    meter_id
                )
                meter["daily_consumption"] = await self.rympro.daily_consumption(
                    meter_id
                )
                meter["consumption_forecast"] = await self.rympro.consumption_forecast(
                    meter_id
                )
        except UnauthorizedError as error:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            raise UpdateFailed(error) from error
        except (CannotConnectError, OperationError) as error:
            raise UpdateFailed(error) from error
        return meters
