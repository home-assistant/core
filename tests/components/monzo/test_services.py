"""Tests for the Monzo component."""

from collections.abc import Callable
from dataclasses import dataclass
from unittest.mock import AsyncMock

from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError
import pytest

from homeassistant.components.monzo.const import DOMAIN
from homeassistant.components.monzo.services import (
    ATTR_AMOUNT,
    SERVICE_POT_TRANSFER,
    TRANSFER_ACCOUNT,
    TRANSFER_POTS,
    TRANSFER_TYPE,
    TRANSFER_TYPE_DEPOSIT,
    TRANSFER_TYPE_WITHDRAWAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceRegistry

from . import setup_integration
from .conftest import TEST_ACCOUNTS, TEST_POTS

from tests.common import MockConfigEntry

EXPECTED_VALUE_GETTERS = {
    "balance": lambda x: x["balance"]["balance"] / 100,
    "total_balance": lambda x: x["balance"]["total_balance"] / 100,
    "pot_balance": lambda x: x["balance"] / 100,
}


async def _make_transfer(
    hass: HomeAssistant,
    account_device_id: str,
    pot_device_ids: list[str],
    transfer_type: str = TRANSFER_TYPE_DEPOSIT,
):
    service_data = {
        TRANSFER_POTS: pot_device_ids,
        TRANSFER_ACCOUNT: account_device_id,
        TRANSFER_TYPE: transfer_type,
        ATTR_AMOUNT: 1.0,
    }

    await hass.services.async_call(
        DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
    )


def _get_device_id_from_account_id(device_registry, pot_id):
    return device_registry.async_get_device(identifiers={(DOMAIN, pot_id)}).id


@dataclass
class ServicesTestData:
    """A collection of data set up by the test_data fixture."""

    hass: HomeAssistant
    device_registry: DeviceRegistry
    account_id: str
    account_device_id: str
    pot_id: str
    pot_device_id: str


@pytest.fixture(autouse=True)
async def test_data(
    hass: HomeAssistant, polling_config_entry: MockConfigEntry, monzo: AsyncMock
) -> None:
    """Set up integration."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)
    account_id = TEST_ACCOUNTS[0]["id"]
    account_device_id = _get_device_id_from_account_id(device_registry, account_id)
    savings_pot_id = TEST_POTS[0]["id"]
    savings_pot_device_id = _get_device_id_from_account_id(
        device_registry, savings_pot_id
    )
    return ServicesTestData(
        hass,
        device_registry,
        account_id,
        account_device_id,
        savings_pot_id,
        savings_pot_device_id,
    )


@pytest.mark.parametrize(
    ("transfer_type", "get_expected_transfer_method"),
    [
        (TRANSFER_TYPE_DEPOSIT, lambda account: account.pot_deposit),
        (TRANSFER_TYPE_WITHDRAWAL, lambda account: account.pot_withdraw),
    ],
)
async def test_basic_pot_transfer(
    transfer_type: str,
    get_expected_transfer_method: Callable[[AsyncMock], AsyncMock],
    test_data: ServicesTestData,
    monzo: AsyncMock,
) -> None:
    """Test basic deposit with pot_transfer."""
    await _make_transfer(
        test_data.hass,
        test_data.account_device_id,
        [test_data.pot_device_id],
        transfer_type,
    )
    get_expected_transfer_method(monzo.user_account).assert_called_once_with(
        test_data.account_id, test_data.pot_id, 1.0 * 100
    )


async def test_deposit_default_account(
    test_data: ServicesTestData, monzo: AsyncMock
) -> None:
    """Test deposit with pot_transfer without specifying an account."""
    service_data = {
        TRANSFER_POTS: [test_data.pot_device_id],
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    await test_data.hass.services.async_call(
        DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
    )
    monzo.user_account.pot_deposit.assert_called_once_with(
        test_data.account_id, test_data.pot_id, 1.0 * 100
    )


async def test_multiple_target_deposit(
    test_data: ServicesTestData, monzo: AsyncMock
) -> None:
    """Test pot_transfer with multiple target pots."""

    pot_ids = [pot["id"] for pot in TEST_POTS]
    pot_device_ids = [
        _get_device_id_from_account_id(test_data.device_registry, pot_id)
        for pot_id in pot_ids
    ]

    await _make_transfer(test_data.hass, test_data.account_device_id, pot_device_ids)
    for pot_id in pot_ids:
        monzo.user_account.pot_deposit.assert_any_call(
            test_data.account_id, pot_id, 1.0 * 100
        )


async def test_transfer_raises_validation_error_if_pots_includes_account(
    test_data: ServicesTestData,
) -> None:
    """Test pot_transfer raises ServiceValidationError if selected pots includes an account."""

    not_pot = TEST_ACCOUNTS[1]
    not_pot_id = not_pot["id"]
    not_pot_device_id = _get_device_id_from_account_id(
        test_data.device_registry, not_pot_id
    )

    with pytest.raises(ServiceValidationError):
        await _make_transfer(
            test_data.hass, test_data.account_device_id, [not_pot_device_id]
        )


async def test_transfer_raises_validation_error_if_account_is_pot(
    test_data: ServicesTestData,
) -> None:
    """Test pot_transfer raises ServiceValidationError if selected account is a pot."""
    with pytest.raises(ServiceValidationError):
        await _make_transfer(
            test_data.hass, test_data.pot_device_id, [test_data.pot_device_id]
        )


async def test_transfer_raises_validation_error_if_no_valid_pots(
    test_data: ServicesTestData,
) -> None:
    """Test pot_transfer raises ServiceValidationError if no valid pots selected."""
    with pytest.raises(ServiceValidationError):
        await _make_transfer(test_data.hass, test_data.account_device_id, [""])


@pytest.mark.parametrize(
    "api_error", [InvalidMonzoAPIResponseError, AuthorisationExpiredError]
)
async def test_external_failure_to_get_current_account_id(
    api_error: Exception,
    test_data: ServicesTestData,
    monzo: AsyncMock,
) -> None:
    """Test pot_transfer raises HomeAssistantError if transfer fails externally."""
    monzo.user_account.accounts.side_effect = api_error
    service_data = {
        TRANSFER_POTS: [test_data.pot_device_id],
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    with pytest.raises(HomeAssistantError):
        await test_data.hass.services.async_call(
            DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
        )


async def test_external_transfer_failure(
    test_data: ServicesTestData,
    monzo: AsyncMock,
) -> None:
    """Test pot_transfer raises HomeAssistantError if transfer fails externally."""
    monzo.user_account.pot_deposit.return_value = False

    with pytest.raises(HomeAssistantError):
        await _make_transfer(
            test_data.hass, test_data.account_device_id, [test_data.pot_device_id]
        )


async def test_transfer_raises_value_error_if_account_is_not_valid_device(
    test_data: ServicesTestData,
) -> None:
    """Test pot_transfer raises ServiceValidationError if account is not a valid device."""

    with pytest.raises(ServiceValidationError):
        await _make_transfer(
            test_data.hass, "invalid_device_id", [test_data.pot_device_id]
        )
