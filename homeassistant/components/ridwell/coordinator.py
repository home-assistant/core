"""Define a Ridwell coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import cast

from aioridwell.client import async_get_client
from aioridwell.errors import InvalidCredentialsError, RidwellError
from aioridwell.model import RidwellAccount, RidwellPickupEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

UPDATE_INTERVAL = timedelta(hours=1)


class RidwellDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, list[RidwellPickupEvent]]]
):
    """Class to manage fetching data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, *, name: str) -> None:
        """Initialize."""
        # These will be filled in by async_initialize; we give them these defaults to
        # avoid arduous typing checks down the line:
        self.accounts: dict[str, RidwellAccount] = {}
        self.dashboard_url = ""
        self.user_id = ""

        super().__init__(hass, LOGGER, name=name, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> dict[str, list[RidwellPickupEvent]]:
        """Fetch the latest data from the source."""
        data = {}

        async def async_get_pickups(account: RidwellAccount) -> None:
            """Get the latest pickups for an account."""
            data[account.account_id] = await account.async_get_pickup_events()

        tasks = [async_get_pickups(account) for account in self.accounts.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, InvalidCredentialsError):
                raise ConfigEntryAuthFailed("Invalid username/password") from result
            if isinstance(result, RidwellError):
                raise UpdateFailed(result) from result

        return data

    async def async_initialize(self) -> None:
        """Initialize the coordinator."""
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            client = await async_get_client(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
                session=session,
            )
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed("Invalid username/password") from err
        except RidwellError as err:
            raise ConfigEntryNotReady(err) from err

        self.accounts = await client.async_get_accounts()
        await self.async_config_entry_first_refresh()

        self.dashboard_url = client.get_dashboard_url()
        self.user_id = cast(str, client.user_id)
