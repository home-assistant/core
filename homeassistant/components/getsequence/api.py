"""API client for Sequence financial orchestration platform."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class SequenceApiError(Exception):
    """Base exception for Sequence API errors."""


class SequenceAuthError(SequenceApiError):
    """Authentication error with Sequence API."""


class SequenceConnectionError(SequenceApiError):
    """Connection error with Sequence API."""


class SequenceApiClient:
    """Client for the Sequence API."""

    def __init__(self, session: aiohttp.ClientSession, access_token: str) -> None:
        """Initialize the API client."""
        self.session = session
        self.access_token = access_token
        self.base_url = API_BASE_URL

    async def async_get_accounts(self) -> dict[str, Any]:
        """Retrieve all accounts (Pods, Income Sources, external accounts)."""
        headers = {
            "x-sequence-access-token": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/accounts"

        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self.session.post(url, headers=headers, json={}) as response:
                    if response.status == 401:
                        raise SequenceAuthError("Invalid access token")
                    if response.status != 200:
                        raise SequenceApiError(
                            f"API request failed with status {response.status}"
                        )

                    data = await response.json()
                    _LOGGER.debug("Retrieved accounts data: %s", data)
                    return data

        except TimeoutError as err:
            raise SequenceConnectionError(
                "Timeout while connecting to Sequence API"
            ) from err
        except aiohttp.ClientError as err:
            raise SequenceConnectionError(
                f"Failed to connect to Sequence API: {err}"
            ) from err

    async def async_test_connection(self) -> bool:
        """Test the connection to the Sequence API."""
        try:
            await self.async_get_accounts()
        except SequenceApiError:
            return False
        else:
            return True

    def get_pod_accounts(self, accounts_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Filter and return only Pod accounts from the accounts data."""
        accounts = accounts_data.get("data", {}).get("accounts", [])
        return [account for account in accounts if account.get("type") == "Pod"]

    def get_income_source_accounts(
        self, accounts_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Filter and return only Income Source accounts from the accounts data."""
        accounts = accounts_data.get("data", {}).get("accounts", [])
        return [
            account for account in accounts if account.get("type") == "Income Source"
        ]

    def get_total_balance(self, accounts_data: dict[str, Any]) -> float:
        """Calculate total balance across all accounts."""
        accounts = accounts_data.get("data", {}).get("accounts", [])
        total = 0.0

        for account in accounts:
            balance_info = account.get("balance", {})
            if (
                balance_info.get("error") is None
                and balance_info.get("amountInDollars") is not None
            ):
                total += balance_info["amountInDollars"]

        return total

    def get_pod_balance(self, accounts_data: dict[str, Any]) -> float:
        """Calculate total balance across all Pod accounts."""
        pod_accounts = self.get_pod_accounts(accounts_data)
        total = 0.0

        for account in pod_accounts:
            balance_info = account.get("balance", {})
            if (
                balance_info.get("error") is None
                and balance_info.get("amountInDollars") is not None
            ):
                total += balance_info["amountInDollars"]

        return total

    def get_liability_accounts(
        self,
        accounts_data: dict[str, Any],
        liability_account_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter and return Liability accounts from the accounts data.

        If liability_account_ids is provided, it will return accounts with those IDs
        (typically External accounts being categorized as liabilities).
        Otherwise, it falls back to filtering by type 'Liability'.
        """
        accounts = accounts_data.get("data", {}).get("accounts", [])

        if liability_account_ids:
            # Use configured account IDs for liability accounts
            # Allow any account type to be categorized as liability
            return [
                account
                for account in accounts
                if str(account.get("id")) in liability_account_ids
            ]

        # Fallback to type-based filtering
        return [account for account in accounts if account.get("type") == "Liability"]

    def get_investment_accounts(
        self,
        accounts_data: dict[str, Any],
        investment_account_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter and return Investment accounts from the accounts data.

        If investment_account_ids is provided, it will return accounts with those IDs
        (typically External accounts being categorized as investments).
        Otherwise, it falls back to filtering by type 'Investment'.
        """
        accounts = accounts_data.get("data", {}).get("accounts", [])

        if investment_account_ids:
            # Use configured account IDs for investment accounts
            # Allow any account type to be categorized as investment
            return [
                account
                for account in accounts
                if str(account.get("id")) in investment_account_ids
            ]

        # Fallback to type-based filtering
        return [account for account in accounts if account.get("type") == "Investment"]

    def get_external_accounts(
        self, accounts_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Filter and return only External accounts from the accounts data."""
        accounts = accounts_data.get("data", {}).get("accounts", [])
        return [
            account
            for account in accounts
            if account.get("type")
            not in ["Pod", "Income Source", "Liability", "Investment"]
        ]

    def get_balance_by_type(
        self, accounts_data: dict[str, Any], account_type: str
    ) -> float:
        """Calculate total balance for accounts of a specific type."""
        accounts = accounts_data.get("data", {}).get("accounts", [])
        total = 0.0

        for account in accounts:
            if account.get("type") == account_type:
                balance_info = account.get("balance", {})
                if (
                    balance_info.get("error") is None
                    and balance_info.get("amountInDollars") is not None
                ):
                    total += balance_info["amountInDollars"]

        return total

    def get_account_types_summary(
        self, accounts_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Get a summary of all account types and their totals."""
        accounts = accounts_data.get("data", {}).get("accounts", [])
        types_summary: dict[str, dict[str, Any]] = {}

        for account in accounts:
            account_type = account.get("type", "Unknown")
            if account_type not in types_summary:
                types_summary[account_type] = {
                    "count": 0,
                    "total_balance": 0.0,
                    "accounts": [],
                }

            balance_info = account.get("balance", {})
            if (
                balance_info.get("error") is None
                and balance_info.get("amountInDollars") is not None
            ):
                types_summary[account_type]["total_balance"] += balance_info[
                    "amountInDollars"
                ]

            types_summary[account_type]["count"] += 1
            types_summary[account_type]["accounts"].append(
                {
                    "id": account.get("id"),
                    "name": account.get("name"),
                    "balance": balance_info.get("amountInDollars"),
                    "error": balance_info.get("error"),
                }
            )

        return types_summary

    def get_configured_liability_balance(
        self,
        accounts_data: dict[str, Any],
        liability_account_ids: list[str] | None = None,
    ) -> float:
        """Calculate total balance for configured liability accounts."""
        # Always include regular Liability type accounts
        total = self.get_balance_by_type(accounts_data, "Liability")

        # Add configured external accounts as liabilities
        if liability_account_ids:
            liability_accounts = self.get_liability_accounts(
                accounts_data, liability_account_ids
            )

            for account in liability_accounts:
                balance_info = account.get("balance", {})
                if (
                    balance_info.get("error") is None
                    and balance_info.get("amountInDollars") is not None
                ):
                    total += balance_info["amountInDollars"]

        return total

    def get_configured_investment_balance(
        self,
        accounts_data: dict[str, Any],
        investment_account_ids: list[str] | None = None,
    ) -> float:
        """Calculate total balance for configured investment accounts."""
        # Always include regular Investment type accounts
        total = self.get_balance_by_type(accounts_data, "Investment")

        # Add configured external accounts as investments
        if investment_account_ids:
            investment_accounts = self.get_investment_accounts(
                accounts_data, investment_account_ids
            )

            for account in investment_accounts:
                balance_info = account.get("balance", {})
                if (
                    balance_info.get("error") is None
                    and balance_info.get("amountInDollars") is not None
                ):
                    total += balance_info["amountInDollars"]

        return total

    def get_uncategorized_external_accounts(
        self,
        accounts_data: dict[str, Any],
        liability_account_ids: list[str] | None = None,
        investment_account_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get external accounts that are not categorized as liabilities or investments."""
        all_external = self.get_external_accounts(accounts_data)

        # Convert to sets for faster lookup
        liability_ids = set(liability_account_ids or [])
        investment_ids = set(investment_account_ids or [])

        return [
            account
            for account in all_external
            if str(account.get("id")) not in liability_ids
            and str(account.get("id")) not in investment_ids
        ]

    def get_uncategorized_external_balance(
        self,
        accounts_data: dict[str, Any],
        liability_account_ids: list[str] | None = None,
        investment_account_ids: list[str] | None = None,
    ) -> float:
        """Calculate total balance for uncategorized external accounts."""
        uncategorized_accounts = self.get_uncategorized_external_accounts(
            accounts_data, liability_account_ids, investment_account_ids
        )

        total = 0.0
        for account in uncategorized_accounts:
            balance_info = account.get("balance", {})
            if (
                balance_info.get("error") is None
                and balance_info.get("amountInDollars") is not None
            ):
                total += balance_info["amountInDollars"]

        return total

    def get_adjusted_total_balance(
        self,
        accounts_data: dict[str, Any],
        liability_account_ids: list[str] | None = None,
        liability_configured: bool = False,
    ) -> float | None:
        """Calculate adjusted total balance treating liabilities as negative values.

        Returns None if liabilities exist but haven't been configured.
        """
        accounts = accounts_data.get("data", {}).get("accounts", [])

        # Check if there are any "Account" type accounts that could be liabilities
        external_accounts = [acc for acc in accounts if acc.get("type") == "Account"]

        # If there are external accounts but liabilities aren't configured, return None
        if external_accounts and not liability_configured:
            return None

        total = 0.0

        for account in accounts:
            balance_info = account.get("balance", {})
            if (
                balance_info.get("error") is None
                and balance_info.get("amountInDollars") is not None
            ):
                balance = balance_info["amountInDollars"]

                # Check if this account is configured as a liability
                if (
                    liability_account_ids
                    and str(account.get("id")) in liability_account_ids
                    and account.get("type") == "Account"
                ):
                    # Liabilities are treated as negative values
                    balance = -balance

                total += balance

        return total
