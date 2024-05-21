"""Tests for the Monzo component."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.monzo.const import DOMAIN
from homeassistant.components.monzo.sensor import MonzoSensorEntityDescription
from homeassistant.components.monzo.services import (
    ATTR_AMOUNT,
    SERVICE_POT_TRANSFER,
    TRANSFER_ACCOUNT,
    TRANSFER_POTS,
    TRANSFER_TYPE,
    TRANSFER_TYPE_DEPOSIT,
    TRANSFER_TYPE_WITHDRAWAL,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import TEST_ACCOUNTS, TEST_POTS

from tests.common import MockConfigEntry

EXPECTED_VALUE_GETTERS = {
    "balance": lambda x: x["balance"]["balance"] / 100,
    "total_balance": lambda x: x["balance"]["total_balance"] / 100,
    "pot_balance": lambda x: x["balance"] / 100,
}


async def async_get_entity_id(
    hass: HomeAssistant,
    acc_id: str,
    description: MonzoSensorEntityDescription,
) -> str | None:
    """Get an entity id for a user's attribute."""
    entity_registry = er.async_get(hass)
    unique_id = f"{acc_id}_{description.key}"

    return entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)


def async_assert_state_equals(
    entity_id: str,
    state_obj: State,
    expected: Any,
    description: MonzoSensorEntityDescription,
) -> None:
    """Assert at given state matches what is expected."""
    assert state_obj, f"Expected entity {entity_id} to exist but it did not"

    assert state_obj.state == str(expected), (
        f"Expected {expected} but was {state_obj.state} "
        f"for measure {description.name}, {entity_id}"
    )


async def test_basic_deposit(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test basic deposit with pot_transfer."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    account_id = TEST_ACCOUNTS[0]["id"]
    account_device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, account_id)}
    ).id
    pot_id = TEST_POTS[0]["id"]
    pot_device_id = device_registry.async_get_device(identifiers={(DOMAIN, pot_id)}).id

    service_data = {
        TRANSFER_POTS: [pot_device_id],
        TRANSFER_ACCOUNT: account_device_id,
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    await hass.services.async_call(
        DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
    )
    monzo.user_account.pot_deposit.assert_called_once_with(
        account_id, pot_id, 1.0 * 100
    )


async def test_basic_withdrawal(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test basic withdrawal with pot_transfer."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    account_id = TEST_ACCOUNTS[0]["id"]
    account_device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, account_id)}
    ).id
    pot_id = TEST_POTS[0]["id"]
    pot_device_id = device_registry.async_get_device(identifiers={(DOMAIN, pot_id)}).id

    service_data = {
        TRANSFER_POTS: [pot_device_id],
        TRANSFER_ACCOUNT: account_device_id,
        TRANSFER_TYPE: TRANSFER_TYPE_WITHDRAWAL,
        ATTR_AMOUNT: 1.0,
    }

    await hass.services.async_call(
        DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
    )
    monzo.user_account.pot_withdraw.assert_called_once_with(
        account_id, pot_id, 1.0 * 100
    )


async def test_deposit_default_account(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test deposit with pot_transfer without specifying an account."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    account_id = TEST_ACCOUNTS[0]["id"]
    pot_id = TEST_POTS[0]["id"]
    pot_device_id = device_registry.async_get_device(identifiers={(DOMAIN, pot_id)}).id

    service_data = {
        TRANSFER_POTS: [pot_device_id],
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    await hass.services.async_call(
        DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
    )
    monzo.user_account.pot_deposit.assert_called_once_with(
        account_id, pot_id, 1.0 * 100
    )


async def test_multiple_target_deposit(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test pot_transfer with multiple target pots."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    account_id = TEST_ACCOUNTS[0]["id"]
    account_device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, account_id)}
    ).id
    pot_ids = [pot["id"] for pot in TEST_POTS]
    pot_device_ids = [
        device_registry.async_get_device(identifiers={(DOMAIN, pot_id)}).id
        for pot_id in pot_ids
    ]

    service_data = {
        TRANSFER_POTS: pot_device_ids,
        TRANSFER_ACCOUNT: account_device_id,
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    await hass.services.async_call(
        DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
    )
    for pot_id in pot_ids:
        monzo.user_account.pot_deposit.assert_any_call(account_id, pot_id, 1.0 * 100)


async def test_transfer_raises_validation_error_if_pots_includes_account(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test pot_transfer raises ServiceValidationError if selected pots includes an account."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    account_id = TEST_ACCOUNTS[0]["id"]
    account_device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, account_id)}
    ).id
    not_pot = TEST_ACCOUNTS[1]
    not_pot_id = not_pot["id"]
    not_pot_device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, not_pot_id)}
    ).id

    service_data = {
        TRANSFER_POTS: [not_pot_device_id],
        TRANSFER_ACCOUNT: account_device_id,
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
        )


async def test_transfer_raises_validation_error_if_account_is_pot(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test pot_transfer raises ServiceValidationError if selected account is a pot."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    not_account = TEST_POTS[0]
    account_id = not_account["id"]
    account_device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, account_id)}
    ).id
    pot_id = TEST_ACCOUNTS[1]["id"]
    pot_device_id = device_registry.async_get_device(identifiers={(DOMAIN, pot_id)}).id

    service_data = {
        TRANSFER_POTS: [pot_device_id],
        TRANSFER_ACCOUNT: account_device_id,
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
        )


async def test_transfer_raises_validation_error_if_no_valid_pots(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test pot_transfer raises ServiceValidationError if no valid pots selected."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    account_id = TEST_ACCOUNTS[0]["id"]
    account_device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, account_id)}
    ).id

    service_data = {
        TRANSFER_POTS: [""],
        TRANSFER_ACCOUNT: account_device_id,
        TRANSFER_TYPE: TRANSFER_TYPE_WITHDRAWAL,
        ATTR_AMOUNT: 1.0,
    }

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
        )


async def test_external_transfer_failure(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test pot_transfer raises HomeAssistantError if transfer fails externally."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    account_id = TEST_ACCOUNTS[0]["id"]
    account_device_id = device_registry.async_get_device(
        identifiers={(DOMAIN, account_id)}
    ).id
    pot_id = TEST_POTS[0]["id"]
    pot_device_id = device_registry.async_get_device(identifiers={(DOMAIN, pot_id)}).id

    service_data = {
        TRANSFER_POTS: [pot_device_id],
        TRANSFER_ACCOUNT: account_device_id,
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    monzo.user_account.pot_deposit.return_value = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
        )


async def test_transfer_raises_value_error_if_account_is_not_valid_device(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test pot_transfer raises ServiceValidationError if account is not a valid device."""
    await setup_integration(hass, polling_config_entry)
    device_registry = dr.async_get(hass)

    pot_id = TEST_ACCOUNTS[1]["id"]
    pot_device_id = device_registry.async_get_device(identifiers={(DOMAIN, pot_id)}).id

    invalid_id = "invalid_device_id"
    service_data = {
        TRANSFER_POTS: [pot_device_id],
        TRANSFER_ACCOUNT: invalid_id,
        TRANSFER_TYPE: TRANSFER_TYPE_DEPOSIT,
        ATTR_AMOUNT: 1.0,
    }

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_POT_TRANSFER, service_data, blocking=True
        )
