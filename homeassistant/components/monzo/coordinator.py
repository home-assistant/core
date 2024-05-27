"""The Monzo integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AuthenticatedMonzoAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class MonzoData:
    """A dataclass for holding sensor data returned by the DataUpdateCoordinator."""

    accounts: list[dict[str, Any]]
    pots: list[dict[str, Any]]


class MonzoCoordinator(DataUpdateCoordinator[MonzoData]):
    """Class to manage fetching Monzo data from the API."""

    def __init__(self, hass: HomeAssistant, api: AuthenticatedMonzoAPI) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self.api = api

    async def _async_update_data(self) -> MonzoData:
        """Fetch data from Monzo API."""
        accounts = await self.api.user_account.accounts()
        pots = await self.api.user_account.pots()
        return MonzoData(accounts, pots)
