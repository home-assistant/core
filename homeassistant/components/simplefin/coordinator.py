"""Data update coordinator for the SimpleFIN integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from simplefin4py import FinancialData, SimpleFin
from simplefin4py.exceptions import SimpleFinAuthError, SimpleFinPaymentRequiredError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


class SimpleFinDataUpdateCoordinator(DataUpdateCoordinator[FinancialData]):
    """Data update coordinator for the SimpleFIN integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: SimpleFin) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name="simplefin",
            update_interval=timedelta(hours=4),
        )
        self.client = client

    async def _async_update_data(self) -> Any:
        """Fetch data for all accounts."""
        try:
            return await self.client.fetch_data()
        except SimpleFinAuthError as err:
            raise ConfigEntryError("Authentication failed") from err

        except SimpleFinPaymentRequiredError as err:
            LOGGER.warning(
                "There is a billing issue with your SimpleFin account, contact Simplefin to address this issue"
            )
            raise UpdateFailed from err
