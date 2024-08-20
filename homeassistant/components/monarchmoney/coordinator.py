"""Data coordinator for monarch money."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from aiohttp import ClientResponseError
from gql.transport.exceptions import TransportServerError
from monarchmoney import LoginFailedException, MonarchMoney

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
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
        self,
        hass: HomeAssistant,
        client: MonarchMoney,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name="monarchmoney",
            update_interval=timedelta(hours=4),
        )
        self.client: MonarchMoney = client
        self.subscription_id: str = "UNSET"

    async def _async_setup(self) -> None:
        """Obtain subscription ID in setup phase."""
        try:
            sub_details = await self.client.get_subscription_details()
        except (TransportServerError, LoginFailedException, ClientResponseError) as err:
            raise ConfigEntryError("Authentication failed") from err

        self.subscription_id = sub_details["subscription"]["id"]

    async def _async_update_data(self) -> MonarchData:
        """Fetch data for all accounts."""

        account_data, cashflow_summary = await asyncio.gather(
            self.client.get_accounts(), self.client.get_cashflow_summary()
        )

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

    @property
    def value_accounts(self) -> list[dict[str, Any]]:
        """Return value accounts."""
        return [
            x
            for x in self.accounts
            if x["type"]["name"]
            in ["real-estate", "vehicle", "valuables", "other_assets"]
        ]

    @property
    def balance_accounts(self) -> list[dict[str, Any]]:
        """Return accounts that aren't assets."""
        return [
            x
            for x in self.accounts
            if x["type"]["name"]
            not in ["real-estate", "vehicle", "valuables", "other_assets"]
        ]

    def get_account_for_id(self, account_id: str) -> dict[str, Any] | None:
        """Get account for id."""
        for account in self.data.account_data:
            if account["id"] == account_id:
                return account
        return None
