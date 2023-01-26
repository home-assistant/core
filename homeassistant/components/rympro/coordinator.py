"""The Read Your Meter Pro integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyrympro import CannotConnectError, OperationError, RymPro, UnauthorizedError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
