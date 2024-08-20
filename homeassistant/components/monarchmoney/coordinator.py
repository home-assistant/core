"""Data coordinator for monarch money."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from monarchmoney import MonarchMoney

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER


@dataclass
class MonarchData:
    """Data class to hold monarch data."""

    account_data: list[dict[str, Any]]
    cashflow_summary: dict[str, Any]


class MonarchMoneyDataUpdateCoordinator(DataUpdateCoordinator[MonarchData]):
    """Data update coordinator for Monarch Money."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, client: MonarchMoney, subscription_id: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name="monarchmoney",
            update_interval=timedelta(hours=4),
        )
        self.client: MonarchMoney = client
        self.subscription_id = subscription_id

    async def _async_update_data(self) -> MonarchData:
        """Fetch data for all accounts."""

        account_data = await self.client.get_accounts()
        cashflow_summary = await self.client.get_cashflow_summary()

        return MonarchData(
            account_data=account_data["accounts"],
            cashflow_summary=cashflow_summary["summary"][0]["summary"],
        )

    @property
    def cashflow_summary(self) -> dict[str, Any]:
        """Return cashflow summary."""
        return self.data.cashflow_summary

    @property
    def accounts(self) -> list[dict[str, Any]]:
        """Return accounts."""

        return self.data.account_data

    def get_account_for_id(self, account_id: str) -> dict[str, Any] | None:
        """Get account for id."""
        for account in self.data.account_data:
            if account["id"] == account_id:
                return account
        return None
