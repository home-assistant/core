"""Data Update Coordinator for Firefly III integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pyfirefly import (
    Firefly,
    FireflyAuthenticationError,
    FireflyConnectionError,
    FireflyTimeoutError,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import FireflyConfigEntry

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)


@dataclass
class FireflyCoordinatorData:
    """Data structure for Firefly III coordinator data."""

    api: Firefly
    accounts: list[dict[str, str]]
    categories: list[dict[str, str]]
    budgets: list[dict[str, str]]
    bills: list[dict[str, str]]


class FireflyDataUpdateCoordinator(DataUpdateCoordinator[FireflyCoordinatorData]):
    """Coordinator to manage data updates for Firefly III integration."""

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
        try:
            # TODO: add the datetime filter later on
            accounts = await self.firefly.get_accounts()
            # categories = await self.firefly.get_categories() # TODO: add categories later, once Github works again
            budgets = await self.firefly.get_budgets()
            bills = await self.firefly.get_bills()

            _LOGGER.debug("Fetched data for accounts: %s", accounts)
            _LOGGER.debug("Fetched data for budgets: %s", budgets)
            _LOGGER.debug("Fetched data for bills: %s", bills)
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

        return FireflyCoordinatorData(
            api=self.firefly,
            accounts=accounts,
            categories=["test", "test"],  # TODO: add this back later on
            budgets=budgets,
            bills=bills,
        )
