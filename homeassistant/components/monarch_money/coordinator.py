"""Data coordinator for monarch money."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, override

from aiohttp import ClientResponseError
from gql.transport.exceptions import TransportServerError
from monarchmoney import LoginFailedException
from typedmonarchmoney import TypedMonarchMoney
from typedmonarchmoney.models import (
    MonarchAccount,
    MonarchCashflowSummary,
    MonarchSubscription,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import LOGGER


@dataclass
class MonarchData:
    """Data class to hold monarch data."""

    account_data: dict[str, MonarchAccount]
    cashflow_summary: MonarchCashflowSummary
    budgets: dict[str, MonarchBudget]
    budget_month_start: datetime


@dataclass
class MonarchBudget:
    """Container for a budget category for a month."""

    id: str
    name: str
    group_name: str
    month: str
    planned_amount: float | None
    actual_amount: float | None
    remaining_amount: float | None


type MonarchMoneyConfigEntry = ConfigEntry[MonarchMoneyDataUpdateCoordinator]


class MonarchMoneyDataUpdateCoordinator(DataUpdateCoordinator[MonarchData]):
    """Data update coordinator for Monarch Money."""

    config_entry: MonarchMoneyConfigEntry
    subscription_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MonarchMoneyConfigEntry,
        client: TypedMonarchMoney,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name="monarchmoney",
            update_interval=timedelta(hours=4),
        )
        self.client = client

    @override
    async def _async_setup(self) -> None:
        """Obtain subscription ID in setup phase."""
        try:
            sub_details: MonarchSubscription = (
                await self.client.get_subscription_details()
            )
        except (TransportServerError, LoginFailedException, ClientResponseError) as err:
            raise ConfigEntryError("Authentication failed") from err
        self.subscription_id = sub_details.id

    @override
    async def _async_update_data(self) -> MonarchData:
        """Fetch account, cashflow, and current budget data."""

        now = dt_util.now()
        budget_month = f"{now.year:04d}-{now.month:02d}"
        budget_start_date = f"{budget_month}-01"
        next_month = now.replace(day=28) + timedelta(days=4)
        budget_end_date = (next_month - timedelta(days=next_month.day)).strftime(
            "%Y-%m-%d"
        )

        account_data, cashflow_summary, raw_budgets = await asyncio.gather(
            self.client.get_accounts_as_dict_with_id_key(),
            self.client.get_cashflow_summary(
                start_date=f"{now.year}-01-01", end_date=f"{now.year}-12-31"
            ),
            self.client.get_budgets(
                start_date=budget_start_date, end_date=budget_end_date
            ),
        )

        return MonarchData(
            account_data=account_data,
            cashflow_summary=cashflow_summary,
            budgets=self._parse_budgets(raw_budgets, budget_month),
            budget_month_start=dt_util.start_of_local_day(now.replace(day=1)),
        )

    @property
    def cashflow_summary(self) -> MonarchCashflowSummary:
        """Return cashflow summary."""
        return self.data.cashflow_summary

    @property
    def accounts(self) -> list[MonarchAccount]:
        """Return accounts."""
        return list(self.data.account_data.values())

    @property
    def value_accounts(self) -> list[MonarchAccount]:
        """Return value accounts."""
        return [x for x in self.accounts if x.is_value_account]

    @property
    def balance_accounts(self) -> list[MonarchAccount]:
        """Return accounts that aren't assets."""
        return [x for x in self.accounts if x.is_balance_account]

    @staticmethod
    def _parse_budgets(
        data: dict[str, Any], budget_month: str
    ) -> dict[str, MonarchBudget]:
        """Return budget categories for the requested month."""
        category_lookup: dict[str, tuple[str, str]] = {}
        for group in data.get("categoryGroups", []):
            for category in group["categories"]:
                category_lookup[category["id"]] = (category["name"], group["name"])

        budgets: dict[str, MonarchBudget] = {}
        for monthly_category in data.get("budgetData", {}).get(
            "monthlyAmountsByCategory", []
        ):
            category_id = monthly_category["category"]["id"]

            month_data = next(
                (
                    amount
                    for amount in monthly_category.get("monthlyAmounts", [])
                    if str(amount.get("month", "")).startswith(budget_month)
                ),
                None,
            )
            if month_data is None:
                continue

            if (category_info := category_lookup.get(category_id)) is None:
                continue

            name, group_name = category_info
            budgets[category_id] = MonarchBudget(
                id=category_id,
                name=name,
                group_name=group_name,
                month=str(month_data["month"]),
                planned_amount=_as_float(month_data["plannedCashFlowAmount"]),
                actual_amount=_as_float(month_data["actualAmount"]),
                remaining_amount=_as_float(month_data["remainingAmount"]),
            )

        return budgets


def _as_float(value: Any) -> float | None:
    """Return a Monarch amount when it is available."""
    if value is None:
        return None
    return float(value)
