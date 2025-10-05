"""DataUpdateCoordinator for Sequence integration."""

from __future__ import annotations

from datetime import timedelta
import json
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .api import SequenceApiClient, SequenceApiError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_INVESTMENT_ACCOUNTS,
    CONF_LIABILITY_ACCOUNTS,
    CONF_LIABILITY_CONFIGURED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SequenceDataUpdateCoordinator(TimestampDataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Sequence API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: aiohttp.ClientSession,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.api = SequenceApiClient(session, entry.data[CONF_ACCESS_TOKEN])
        self.entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via Sequence API."""
        try:
            accounts_data = await self.api.async_get_accounts()

            # Debug: Dump the raw JSON payload from Sequence API
            _LOGGER.debug("=== RAW SEQUENCE API RESPONSE START ===")
            _LOGGER.debug(json.dumps(accounts_data, indent=2, default=str))
            _LOGGER.debug("=== RAW SEQUENCE API RESPONSE END ===")

            # Get configured account lists from options
            liability_account_ids = self.entry.options.get(CONF_LIABILITY_ACCOUNTS, [])
            investment_account_ids = self.entry.options.get(
                CONF_INVESTMENT_ACCOUNTS, []
            )

            # Check if liabilities have been configured (either with accounts or explicitly as none)
            liability_configured = bool(
                liability_account_ids
            ) or self.entry.options.get(CONF_LIABILITY_CONFIGURED, False)

            # Process and organize the data for easy access by entities
            processed_data = {
                "accounts": accounts_data,
                "pods": self.api.get_pod_accounts(accounts_data),
                "income_sources": self.api.get_income_source_accounts(accounts_data),
                "liabilities": self.api.get_liability_accounts(
                    accounts_data, liability_account_ids
                ),
                "investments": self.api.get_investment_accounts(
                    accounts_data, investment_account_ids
                ),
                "external_accounts": self.api.get_external_accounts(accounts_data),
                "uncategorized_external_accounts": self.api.get_uncategorized_external_accounts(
                    accounts_data, liability_account_ids, investment_account_ids
                ),
                "total_balance": self.api.get_adjusted_total_balance(
                    accounts_data, liability_account_ids, liability_configured
                )
                or self.api.get_total_balance(accounts_data),
                "pod_balance": self.api.get_pod_balance(accounts_data),
                "liability_balance": self.api.get_configured_liability_balance(
                    accounts_data, liability_account_ids
                ),
                "investment_balance": self.api.get_configured_investment_balance(
                    accounts_data, investment_account_ids
                ),
                "income_source_balance": self.api.get_balance_by_type(
                    accounts_data, "Income Source"
                ),
                "uncategorized_external_balance": self.api.get_uncategorized_external_balance(
                    accounts_data, liability_account_ids, investment_account_ids
                ),
                "account_types_summary": self.api.get_account_types_summary(
                    accounts_data
                ),
                "last_updated": self.last_update_success_time
                if hasattr(self, "last_update_success_time")
                else None,
                "raw_data": accounts_data,
            }

            # Debug logging to help identify account type issues
            all_accounts = accounts_data.get("data", {}).get("accounts", [])
            account_types = {acc.get("type") for acc in all_accounts}
            _LOGGER.debug("Account types found: %s", account_types)

            # Log detailed account structure for each type
            for account in all_accounts:
                _LOGGER.debug(
                    "Account: id=%s, name='%s', type='%s', balance=%s",
                    account.get("id"),
                    account.get("name"),
                    account.get("type"),
                    account.get("balance", {}).get("amountInDollars"),
                )

            _LOGGER.debug("Liability balance: %s", processed_data["liability_balance"])
            _LOGGER.debug(
                "Investment balance: %s", processed_data["investment_balance"]
            )
            liabilities = processed_data["liabilities"]
            investments = processed_data["investments"]
            external_accounts = processed_data["external_accounts"]
            assert isinstance(liabilities, list)
            assert isinstance(investments, list)
            assert isinstance(external_accounts, list)
            _LOGGER.debug("Liabilities count: %s", len(liabilities))
            _LOGGER.debug("Investments count: %s", len(investments))
            _LOGGER.debug("External accounts count: %s", len(external_accounts))

            # Debug specific account lists
            if liabilities:
                _LOGGER.debug(
                    "Liability accounts: %s",
                    [
                        {
                            "id": acc.get("id"),
                            "name": acc.get("name"),
                            "type": acc.get("type"),
                        }
                        for acc in liabilities
                    ],
                )
            if investments:
                _LOGGER.debug(
                    "Investment accounts: %s",
                    [
                        {
                            "id": acc.get("id"),
                            "name": acc.get("name"),
                            "type": acc.get("type"),
                        }
                        for acc in investments
                    ],
                )

            _LOGGER.debug("Updated data: %s", processed_data)
        except SequenceApiError as err:
            raise UpdateFailed(f"Error communicating with Sequence API: {err}") from err
        else:
            return processed_data
