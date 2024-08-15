"""Data coordinator for monarch money."""

from datetime import timedelta
from typing import Any

from monarchmoney import MonarchMoney

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER

AccountData = dict[str, Any]


class MonarchMoneyDataUpdateCoordinator(DataUpdateCoordinator[AccountData]):
    """Data update coordinator for Monarch Money."""

    config_entry: ConfigEntry

    def __init__(self, hass, client):
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name="monarchmoney",
            update_interval=timedelta(hours=4),
        )
        self.client: MonarchMoney = client

    async def _async_update_data(self) -> Any:
        """Fetch data for all accounts."""

        return await self.client.get_accounts()

    @property
    def accounts(self) -> Any:
        """Return accounts."""
        return self.data["accounts"]

    def get_account_for_id(self, account_id: str) -> Any | None:
        """Get account for id."""
        for account in self.data["accounts"]:
            if account["id"] == account_id:
                return account
        return None
