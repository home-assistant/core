"""Tests for the FinTS client."""

from fints.client import BankIdentifier, FinTSOperations
import pytest

from homeassistant.components.fints.sensor import (
    BankCredentials,
    FinTsClient,
    SEPAAccount,
)

BANK_INFORMATION = {
    "bank_identifier": BankIdentifier(country_identifier="280", bank_code="50010517"),
    "currency": "EUR",
    "customer_id": "0815",
    "owner_name": ["SURNAME, FIRSTNAME"],
    "subaccount_number": None,
    "supported_operations": {
        FinTSOperations.GET_BALANCE: True,
        FinTSOperations.GET_CREDIT_CARD_TRANSACTIONS: False,
        FinTSOperations.GET_HOLDINGS: False,
        FinTSOperations.GET_SCHEDULED_DEBITS_MULTIPLE: False,
        FinTSOperations.GET_SCHEDULED_DEBITS_SINGLE: False,
        FinTSOperations.GET_SEPA_ACCOUNTS: True,
        FinTSOperations.GET_STATEMENT: False,
        FinTSOperations.GET_STATEMENT_PDF: False,
        FinTSOperations.GET_TRANSACTIONS: True,
        FinTSOperations.GET_TRANSACTIONS_XML: False,
    },
}


@pytest.mark.parametrize(
    (
        "account_number",
        "iban",
        "product_name",
        "account_type",
        "expected_balance_result",
        "expected_holdings_result",
    ),
    [
        ("GIRO1", "GIRO1", "Valid balance account", 5, True, False),
        (None, None, "Invalid account", None, False, False),
        ("GIRO2", "GIRO2", "Account without type", None, False, False),
        ("GIRO3", "GIRO3", "Balance account from fallback", None, True, False),
        ("DEPOT1", "DEPOT1", "Valid holdings account", 33, False, True),
        ("DEPOT2", "DEPOT2", "Holdings account from fallback", None, False, True),
    ],
)
async def test_account_type(
    account_number: str | None,
    iban: str | None,
    product_name: str,
    account_type: int | None,
    expected_balance_result: bool,
    expected_holdings_result: bool,
) -> None:
    """Check client methods is_balance_account and is_holdings_account."""
    credentials = BankCredentials(
        blz=1234, login="test", pin="0000", url="https://example.com"
    )
    account_config = {"GIRO3": True}
    holdings_config = {"DEPOT2": True}

    client = FinTsClient(
        credentials=credentials,
        name="test",
        account_config=account_config,
        holdings_config=holdings_config,
    )

    client._account_information_fetched = True
    client._account_information = {
        iban: BANK_INFORMATION
        | {
            "account_number": account_number,
            "iban": iban,
            "product_name": product_name,
            "type": account_type,
        }
    }

    sepa_account = SEPAAccount(
        iban=iban,
        bic="BANCODELTEST",
        accountnumber=account_number,
        subaccount=None,
        blz="12345",
    )

    assert client.is_balance_account(sepa_account) == expected_balance_result
    assert client.is_holdings_account(sepa_account) == expected_holdings_result
