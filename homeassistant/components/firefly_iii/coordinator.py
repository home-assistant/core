"""Data Update Coordinator for Firefly III integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from aiohttp import CookieJar
from pyfirefly import (
    Firefly,
    FireflyAuthenticationError,
    FireflyConnectionError,
    FireflyTimeoutError,
)
from pyfirefly.models import Account, Bill, Budget, Category, Currency

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type FireflyConfigEntry = ConfigEntry[FireflyDataUpdateCoordinator]

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)


@dataclass
class FireflyCoordinatorData:
    """Data structure for Firefly III coordinator data."""

    accounts: list[Account]
    categories: list[Category]
    category_details: list[Category]
    budgets: list[Budget]
    bills: list[Bill]
    primary_currency: Currency


class FireflyDataUpdateCoordinator(DataUpdateCoordinator[FireflyCoordinatorData]):
    """Coordinator to manage data updates for Firefly III integration."""

    config_entry: FireflyConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: FireflyConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.firefly = Firefly(
            api_url=self.config_entry.data[CONF_URL],
            api_key=self.config_entry.data[CONF_API_KEY],
            session=async_create_clientsession(
                self.hass,
                self.config_entry.data[CONF_VERIFY_SSL],
                cookie_jar=CookieJar(unsafe=True),
            ),
        )

    async def _async_setup(self) -> None:
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
        now = datetime.now()
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now

        try:
            accounts = await self.firefly.get_accounts()
            categories = await self.firefly.get_categories()
            category_details = [
                await self.firefly.get_category(
                    category_id=int(category.id), start=start_date, end=end_date
                )
                for category in categories
            ]
            primary_currency = await self.firefly.get_currency_primary()
            budgets = await self.firefly.get_budgets()
            bills = await self.firefly.get_bills()
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
            accounts=accounts,
            categories=categories,
            category_details=category_details,
            budgets=budgets,
            bills=bills,
            primary_currency=primary_currency,
        )
