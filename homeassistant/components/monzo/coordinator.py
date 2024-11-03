"""The Monzo integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from pprint import pformat
from typing import Any

from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
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
        try:
            accounts = await self.api.user_account.accounts()
            pots = await self.api.user_account.pots()
        except AuthorisationExpiredError as err:
            raise ConfigEntryAuthFailed from err
        except InvalidMonzoAPIResponseError as err:
            message = "Invalid Monzo API response."
            if err.missing_key:
                message += f"\nMissing key: {err.missing_key} Response:\n{pformat(err.response)}"
            raise HomeAssistantError(message) from err

        return MonzoData(accounts, pots)
