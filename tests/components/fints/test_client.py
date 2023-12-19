"""Tests for the FinTS client."""

from fints.client import BankIdentifier, FinTSOperations

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

VALID_ACCOUNT_INFORMATION = BANK_INFORMATION | {
    "account_number": "123456789",
    "iban": "DE00123456789123456789",
    "product_name": "Super Konto",
    "type": 5,
}

NO_TYPE_INFORMATION = BANK_INFORMATION | {
    "account_number": "123456789",
    "iban": "DE1234567890123456789",
    "product_name": "Account without type",
    "type": None,
}

ACCOUNT_CONFIG_FALLBACK_INFORMATION = BANK_INFORMATION | {
    "account_number": "123456789",
    "iban": "DE081512345678912",
    "product_name": "Account without type with fallback",
    "type": None,
}


async def test_fints_client_is_balance_account() -> None:
    """Check method is_balance_account."""

    credentials = BankCredentials(
        blz=1234, login="test", pin="0000", url="https://example.com"
    )
    account_config = {"DE081512345678912": True}
    holdings_config = {}

    client = FinTsClient(
        credentials=credentials,
        name="test",
        account_config=account_config,
        holdings_config=holdings_config,
    )

    client._account_information_fetched = True
    client._account_information = {
        "DE00123456789123456789": VALID_ACCOUNT_INFORMATION,
        "DE1234567890123456789": NO_TYPE_INFORMATION,
        "DE081512345678912": ACCOUNT_CONFIG_FALLBACK_INFORMATION,
    }

    valid_account = SEPAAccount(
        iban="DE00123456789123456789",
        bic="BANCODELTEST",
        accountnumber="123456789",
        subaccount=None,
        blz="12345",
    )
    invalid_account = SEPAAccount(
        iban=None, bic=None, accountnumber=None, subaccount=None, blz=None
    )
    no_type = SEPAAccount(
        iban="DE1234567890123456789",
        bic="BANCODELTEST",
        accountnumber="123456789",
        subaccount=None,
        blz="12345",
    )
    account_config_fallback = SEPAAccount(
        iban="DE081512345678912",
        bic="BANCODELTEST",
        accountnumber="123456789",
        subaccount=None,
        blz="12345",
    )

    assert client.is_balance_account(valid_account)
    assert not client.is_balance_account(invalid_account)
    assert not client.is_balance_account(no_type)
    assert client.is_balance_account(account_config_fallback)


VALID_HOLDINGS_INFORMATION = BANK_INFORMATION | {
    "account_number": "123456789",
    "iban": "DE00123456789123456789",
    "product_name": "Super Depot",
    "type": 33,
}

HOLDINGS_CONFIG_FALLBACK_INFORMATION = BANK_INFORMATION | {
    "account_number": "DEPOT",
    "iban": "DEPOT",
    "product_name": "Account without type with fallback",
    "type": None,
}


async def test_fints_client_is_holdings_account() -> None:
    """Check method is_holdings_account."""

    credentials = BankCredentials(
        blz=1234, login="test", pin="0000", url="https://example.com"
    )
    account_config = {}
    holdings_config = {"DEPOT": True}

    client = FinTsClient(
        credentials=credentials,
        name="test",
        account_config=account_config,
        holdings_config=holdings_config,
    )

    client._account_information_fetched = True
    client._account_information = {
        "DE00123456789123456789": VALID_HOLDINGS_INFORMATION,
        "DE1234567890123456789": NO_TYPE_INFORMATION,
        "DEPOT": HOLDINGS_CONFIG_FALLBACK_INFORMATION,
    }

    valid_account = SEPAAccount(
        iban="DE00123456789123456789",
        bic="BANCODELTEST",
        accountnumber="123456789",
        subaccount=None,
        blz="12345",
    )
    invalid_account = SEPAAccount(
        iban=None, bic=None, accountnumber=None, subaccount=None, blz=None
    )
    no_type = SEPAAccount(
        iban="DE1234567890123456789",
        bic="BANCODELTEST",
        accountnumber="123456789",
        subaccount=None,
        blz="12345",
    )
    account_config_fallback = SEPAAccount(
        iban="DEPOT",
        bic="BANCODELTEST",
        accountnumber="DEPOT",
        subaccount=None,
        blz="12345",
    )

    assert client.is_holdings_account(valid_account)
    assert not client.is_holdings_account(invalid_account)
    assert not client.is_holdings_account(no_type)
    assert client.is_holdings_account(account_config_fallback)
