"""Tests for the FinTS sensor platform."""

import logging
from unittest.mock import MagicMock, patch

from fints.client import BankIdentifier, FinTSOperations
import pytest

from homeassistant.components.fints.sensor import SEPAAccount
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

BANK_INFORMATION = {
    "bank_identifier": BankIdentifier(country_identifier="280", bank_code="50010517"),
    "currency": "EUR",
    "customer_id": "0815",
    "owner_name": ["SURNAME, FIRSTNAME"],
    "subaccount_number": None,
    "supported_operations": {
        FinTSOperations.GET_BALANCE: True,
        FinTSOperations.GET_HOLDINGS: True,
        FinTSOperations.GET_SEPA_ACCOUNTS: True,
    },
}

# GIRO2 and DEPOT2 are deliberately left out of the configuration below, so the
# platform skips them. UNKNOWN has no type and matches neither config.
ACCOUNT_TYPES = {"GIRO1": 5, "GIRO2": 5, "DEPOT1": 33, "DEPOT2": 33, "UNKNOWN": None}

CONFIG = {
    "sensor": {
        "platform": "fints",
        "bank_identification_number": "12345678",
        "username": "user",
        "pin": "1234",
        "url": "https://example.com",
        "name": "Test Bank",
        "accounts": [{"account": "GIRO1", "name": "Checking"}],
        "holdings": [{"account": "DEPOT1", "name": "Depot"}],
    }
}


def _sepa_account(identifier: str) -> SEPAAccount:
    """Build a SEPA account with the same IBAN and account number."""
    return SEPAAccount(
        iban=identifier,
        bic="BANCODELTEST",
        accountnumber=identifier,
        subaccount=None,
        blz="12345",
    )


@pytest.fixture
def mock_bank() -> MagicMock:
    """Return a bank that serves one of every account we care about."""
    bank = MagicMock()
    bank.get_sepa_accounts.return_value = [
        _sepa_account(identifier) for identifier in ACCOUNT_TYPES
    ]
    bank.get_information.return_value = {
        "accounts": [
            BANK_INFORMATION
            | {"account_number": identifier, "iban": identifier, "type": account_type}
            for identifier, account_type in ACCOUNT_TYPES.items()
        ]
    }
    bank.get_balance.return_value.amount.amount = 1234.56
    bank.get_balance.return_value.amount.currency = "EUR"
    bank.get_holdings.return_value = []
    return bank


async def test_setup_platform(
    hass: HomeAssistant, mock_bank: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Only configured accounts get a sensor, and the rest are skipped."""
    caplog.set_level(logging.DEBUG)

    with patch(
        "homeassistant.components.fints.sensor.FinTS3PinTanClient",
        return_value=mock_bank,
    ):
        assert await async_setup_component(hass, "sensor", CONFIG)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.checking").state == "1234.56"
    assert hass.states.get("sensor.depot").state == "0"

    assert "Skipping account for bank Test Bank" in caplog.text
    assert "Skipping holdings for bank Test Bank" in caplog.text
    assert "Could not determine type of account for bank Test Bank" in caplog.text


async def test_account_identifiers_are_not_logged(
    hass: HomeAssistant, mock_bank: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """No IBAN or account number ends up in the log of this integration."""
    caplog.set_level(logging.DEBUG)

    with patch(
        "homeassistant.components.fints.sensor.FinTS3PinTanClient",
        return_value=mock_bank,
    ):
        assert await async_setup_component(hass, "sensor", CONFIG)
        await hass.async_block_till_done()

    # The identifiers are state attributes, which the event bus dumps as part of
    # the state changed events it logs when debug logging is on. Only the log of
    # this integration is of interest here.
    logged = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("homeassistant.components.fints")
    )

    for identifier in ACCOUNT_TYPES:
        assert identifier not in logged
