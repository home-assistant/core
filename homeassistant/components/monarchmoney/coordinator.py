"""Data coordinator for monarch money."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
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
class MonarchAccount:
    """Dataclass to store & parse account data from monarch accounts."""

    id: str
    logo_url: str | None
    name: str
    balance: float
    type: str  # type will be used for icons
    type_name: str  # type name will be used for device
    subtype: str
    subtype_name: str
    data_provider: str
    institution_url: str | None
    institution_name: str | None
    last_update: datetime
    date_created: datetime

    @property
    def is_value_account(self):
        """Return true if we are tracking a value type asset."""
        return self.type in ["real-estate", "vehicle", "valuables", "other_assets"]

    @property
    def is_balance_account(self):
        """Whether to show a balance sensor or a value sensor."""
        return not self.is_value_account


@dataclass
class MonarchCashflow:
    """Cashflow data class."""

    income: float
    expenses: float
    savings: float
    savings_rate: float


@dataclass
class MonarchData:
    """Data class to hold monarch data."""

    account_data: list[MonarchAccount]
    cashflow_summary: MonarchCashflow


def _build_cashflow(data: dict[str, Any]) -> MonarchCashflow:
    """Build a monarch cashflow object."""
    return MonarchCashflow(
        income=data["sumIncome"],
        expenses=data["sumExpense"],
        savings=data["savings"],
        savings_rate=data["savingsRate"],
    )


def _build_monarch_account(data: dict[str, Any]) -> MonarchAccount:
    """Build a monarch account object."""
    institution = data.get("institution") or {}
    credential = data.get("credential") or {}

    return MonarchAccount(
        id=data["id"],
        logo_url=data.get("logoUrl"),
        name=data["displayName"],
        balance=data["currentBalance"],
        type=data["type"]["name"],
        type_name=data["type"]["display"],
        subtype=data["subtype"]["name"],
        subtype_name=data["subtype"]["display"],
        data_provider=credential.get("dataProvider", "Manual entry"),
        last_update=datetime.fromisoformat(data["updatedAt"]),
        date_created=datetime.fromisoformat(data["createdAt"]),
        institution_url=institution.get("url", None),
        institution_name=institution.get("name", "Manual entry"),
    )


class MonarchMoneyDataUpdateCoordinator(DataUpdateCoordinator[MonarchData]):
    """Data update coordinator for Monarch Money."""

    config_entry: ConfigEntry
    subscription_id: str

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
        self.client = client
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
            account_data=[
                _build_monarch_account(acc) for acc in account_data["accounts"]
            ],
            cashflow_summary=_build_cashflow(cashflow_summary["summary"][0]["summary"]),
        )

    @property
    def cashflow_summary(self) -> MonarchCashflow:
        """Return cashflow summary."""
        return self.data.cashflow_summary

    @property
    def accounts(self) -> list[MonarchAccount]:
        """Return accounts."""

        return self.data.account_data

    @property
    def value_accounts(self) -> list[MonarchAccount]:
        """Return value accounts."""
        return [x for x in self.accounts if x.is_value_account]

    @property
    def balance_accounts(self) -> list[MonarchAccount]:
        """Return accounts that aren't assets."""
        return [x for x in self.accounts if x.is_balance_account]

    def get_account_for_id(self, account_id: str) -> MonarchAccount | None:
        """Get account for id."""
        for account in self.data.account_data:
            if account.id == account_id:
                return account
        return None
