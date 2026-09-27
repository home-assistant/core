"""Data coordinator for monarch money."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Never, override

from aiohttp import ClientError, ClientResponseError
from gql.transport.exceptions import TransportError, TransportServerError
from monarchmoney import LoginFailedException
from typedmonarchmoney import TypedMonarchMoney
from typedmonarchmoney.models import (
    MonarchAccount,
    MonarchCashflowSummary,
    MonarchSubscription,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import LOGGER


@dataclass
class MonarchData:
    """Data class to hold monarch data."""

    account_data: dict[str, MonarchAccount]
    cashflow_summary: MonarchCashflowSummary


type MonarchMoneyConfigEntry = ConfigEntry[MonarchMoneyDataUpdateCoordinator]


def _raise_update_error(err: Exception) -> Never:
    """Translate Monarch Money API errors to coordinator errors."""
    if isinstance(err, LoginFailedException) or (
        isinstance(err, (TransportServerError, ClientResponseError))
        and (err.status if isinstance(err, ClientResponseError) else err.code)
        in (401, 403)
    ):
        raise ConfigEntryAuthFailed("Authentication failed") from err
    raise UpdateFailed("Error communicating with Monarch Money") from err


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
        except (LoginFailedException, TransportError, ClientError, TimeoutError) as err:
            _raise_update_error(err)
        self.subscription_id = sub_details.id

    @override
    async def _async_update_data(self) -> MonarchData:
        """Fetch data for all accounts."""

        now = dt_util.now()

        try:
            account_data, cashflow_summary = await asyncio.gather(
                self.client.get_accounts_as_dict_with_id_key(),
                self.client.get_cashflow_summary(
                    start_date=f"{now.year}-01-01", end_date=f"{now.year}-12-31"
                ),
            )
        except (LoginFailedException, TransportError, ClientError, TimeoutError) as err:
            _raise_update_error(err)

        return MonarchData(account_data=account_data, cashflow_summary=cashflow_summary)

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
