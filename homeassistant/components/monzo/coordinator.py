"""The Monzo integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from pprint import pformat
from typing import Any

from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
                _LOGGER.debug(
                    "%s\nMissing key: %s\nResponse:\n%s",
                    message,
                    err.missing_key,
                    pformat(err.response),
                )
                message += " Enabling debug logging for details."
            raise UpdateFailed(message) from err

        return MonzoData(accounts, pots)
