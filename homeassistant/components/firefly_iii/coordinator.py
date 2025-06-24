"""Data Update Coordinator for Firefly III integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import TYPE_CHECKING

from pyfirefly import (
    Firefly,
    FireflyAuthenticationError,
    FireflyConnectionError,
    FireflyTimeoutError,
)
from pyfirefly.models import Account, Bill, Budget, Category, Currency

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import FireflyConfigEntry

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)


@dataclass
class FireflyCoordinatorData:
    """Data structure for Firefly III coordinator data."""

    api: Firefly
    accounts: list[Account]
    categories: list[Category]
    category_details: list[Category]
    budgets: list[Budget]
    bills: list[Bill]
    native_currency: Currency


class FireflyDataUpdateCoordinator(DataUpdateCoordinator[FireflyCoordinatorData]):
    """Coordinator to manage data updates for Firefly III integration."""

    config_entry: FireflyConfigEntry
    def __init__(
        self, hass: HomeAssistant, config_entry: FireflyConfigEntry, firefly: Firefly
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.firefly = firefly

    async def _async_setup(self):
        """Set up the coordinator."""
        try:
            await self.firefly.get_about()
        except FireflyAuthenticationError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except FireflyConnectionError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except FireflyTimeoutError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def _async_update_data(self) -> FireflyCoordinatorData:
        """Fetch data from Firefly III API."""
        end_date = date.today()
        start_date = end_date.replace(day=1)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        try:
            accounts = await self.firefly.get_accounts()
            categories = await self.firefly.get_categories()
            category_details: list[Category] = [
                await self.firefly.get_category(
                    category_id=int(category.id), start=start_str, end=end_str
                )
                for category in categories
            ]
            native_currency = await self.firefly.get_currency_native()
            budgets = await self.firefly.get_budgets()
            bills = await self.firefly.get_bills()

            _LOGGER.debug("Fetched data for native currency: %s", native_currency)
        except FireflyAuthenticationError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except FireflyConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except FireflyTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
                translation_placeholders={"error": repr(err)},
            ) from err

        return FireflyCoordinatorData(
            api=self.firefly,
            accounts=accounts,
            categories=categories,
            category_details=category_details,
            budgets=budgets,
            bills=bills,
            native_currency=native_currency,
        )
