"""Tests for Monzo actions."""

from collections.abc import Callable
from dataclasses import dataclass
from math import nan
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError
import pytest
import voluptuous as vol

from homeassistant.components.monzo.const import (
    DEVICE_MODEL_ACCOUNT,
    DEVICE_MODEL_POT,
    DOMAIN,
)
from homeassistant.components.monzo.services import (
    ATTR_ACCOUNT,
    ATTR_AMOUNT,
    ATTR_POT,
    SERVICE_DEPOSIT_INTO_POT,
    SERVICE_WITHDRAW_FROM_POT,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestReauthError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import TEST_ACCOUNTS, TEST_POTS

from tests.common import MockConfigEntry, MockUser


@dataclass
class TransferDevices:
    """Devices used to test pot transfers."""

    account_id: str
    account_device_id: str
    pot_id: str
    pot_device_id: str


@pytest.fixture
async def transfer_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
) -> TransferDevices:
    """Set up Monzo and return its account and pot devices."""
    await setup_integration(hass, polling_config_entry)
    account_id = cast(str, TEST_ACCOUNTS[0]["id"])
    pot_id = cast(str, TEST_POTS[0]["id"])
    account_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, account_id), polling_config_entry.entry_id
    )
    pot_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, pot_id), polling_config_entry.entry_id
    )
    assert account_device is not None
    assert pot_device is not None
    return TransferDevices(account_id, account_device.id, pot_id, pot_device.id)


async def _async_call_transfer(
    hass: HomeAssistant,
    devices: TransferDevices,
    service_name: str,
    amount: object = 0.29,
) -> None:
    """Call a Monzo pot transfer action."""
    await hass.services.async_call(
        DOMAIN,
        service_name,
        {
            ATTR_ACCOUNT: devices.account_device_id,
            ATTR_POT: devices.pot_device_id,
            ATTR_AMOUNT: amount,
        },
        blocking=True,
    )


async def test_device_models_support_selector_filtering(
    device_registry: dr.DeviceRegistry,
    transfer_devices: TransferDevices,
) -> None:
    """Test account and pot devices can be filtered in action selectors."""
    account_device = device_registry.async_get(transfer_devices.account_device_id)
    pot_device = device_registry.async_get(transfer_devices.pot_device_id)
    assert account_device is not None
    assert pot_device is not None
    assert account_device.model == DEVICE_MODEL_ACCOUNT
    assert pot_device.model == DEVICE_MODEL_POT


async def test_non_transfer_account_is_rejected(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    polling_config_entry: MockConfigEntry,
    transfer_devices: TransferDevices,
) -> None:
    """Test an account product which does not support pot transfers is rejected."""
    flex_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, cast(str, TEST_ACCOUNTS[1]["id"])), polling_config_entry.entry_id
    )
    assert flex_device is not None
    assert flex_device.model == "Flex"

    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DEPOSIT_INTO_POT,
            {
                ATTR_ACCOUNT: flex_device.id,
                ATTR_POT: transfer_devices.pot_device_id,
                ATTR_AMOUNT: 1,
            },
            blocking=True,
        )

    assert error.value.translation_key == "invalid_transfer_account"


@pytest.mark.parametrize(
    ("service_name", "transfer_method"),
    [
        (SERVICE_DEPOSIT_INTO_POT, lambda account: account.pot_deposit),
        (SERVICE_WITHDRAW_FROM_POT, lambda account: account.pot_withdraw),
    ],
)
async def test_transfer_and_refresh(
    hass: HomeAssistant,
    monzo: AsyncMock,
    transfer_devices: TransferDevices,
    service_name: str,
    transfer_method: Callable[[AsyncMock], AsyncMock],
) -> None:
    """Test transfers use exact minor units and refresh Monzo data."""
    await _async_call_transfer(hass, transfer_devices, service_name)

    transfer_method(monzo.user_account).assert_awaited_once_with(
        transfer_devices.account_id,
        transfer_devices.pot_id,
        29,
    )
    assert monzo.user_account.accounts.await_count == 2
    assert monzo.user_account.pots.await_count == 2


@pytest.mark.parametrize(
    "amount",
    [
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative"),
        pytest.param(0.001, id="too-many-decimal-places"),
        pytest.param("invalid", id="not-a-number"),
        pytest.param(nan, id="non-finite"),
        pytest.param("1e999999", id="decimal-overflow"),
        pytest.param("1e-10000000", id="minor-units-underflow"),
    ],
)
async def test_invalid_amount(
    hass: HomeAssistant,
    transfer_devices: TransferDevices,
    amount: object,
) -> None:
    """Test invalid transfer amounts are rejected by the action schema."""
    with pytest.raises(vol.Invalid):
        await _async_call_transfer(
            hass,
            transfer_devices,
            SERVICE_DEPOSIT_INTO_POT,
            amount,
        )


@pytest.mark.parametrize(
    ("account_device", "pot_device", "translation_key"),
    [
        ("pot_device_id", "pot_device_id", "pot_selected_as_account"),
        ("account_device_id", "account_device_id", "account_selected_as_pot"),
    ],
)
async def test_invalid_resource_type(
    hass: HomeAssistant,
    transfer_devices: TransferDevices,
    account_device: str,
    pot_device: str,
    translation_key: str,
) -> None:
    """Test selected devices must represent an account and a pot."""
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DEPOSIT_INTO_POT,
            {
                ATTR_ACCOUNT: getattr(transfer_devices, account_device),
                ATTR_POT: getattr(transfer_devices, pot_device),
                ATTR_AMOUNT: 1,
            },
            blocking=True,
        )

    assert error.value.translation_key == translation_key


async def test_missing_device(
    hass: HomeAssistant,
    transfer_devices: TransferDevices,
) -> None:
    """Test a missing selected device is rejected."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DEPOSIT_INTO_POT,
            {
                ATTR_ACCOUNT: "missing-device",
                ATTR_POT: transfer_devices.pot_device_id,
                ATTR_AMOUNT: 1,
            },
            blocking=True,
        )


async def test_devices_from_different_entries(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    transfer_devices: TransferDevices,
) -> None:
    """Test the account and pot must belong to the same config entry."""
    other_entry = MockConfigEntry(domain=DOMAIN)
    other_entry.add_to_hass(hass)
    other_pot = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, "other-pot")},
        name="Other pot",
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DEPOSIT_INTO_POT,
            {
                ATTR_ACCOUNT: transfer_devices.account_device_id,
                ATTR_POT: other_pot.id,
                ATTR_AMOUNT: 1,
            },
            blocking=True,
        )


async def test_pot_must_belong_to_selected_account(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    polling_config_entry: MockConfigEntry,
    transfer_devices: TransferDevices,
) -> None:
    """Test a pot can only be transferred to or from its owning account."""
    joint_account_id = "acc_joint"
    polling_config_entry.runtime_data.coordinator.data.accounts[joint_account_id] = {
        "id": joint_account_id,
        "name": "Joint Account",
        "type": "uk_retail_joint",
    }
    joint_account = device_registry.async_get_or_create(
        config_entry_id=polling_config_entry.entry_id,
        identifiers={(DOMAIN, joint_account_id)},
        name="Joint Account",
    )

    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DEPOSIT_INTO_POT,
            {
                ATTR_ACCOUNT: joint_account.id,
                ATTR_POT: transfer_devices.pot_device_id,
                ATTR_AMOUNT: 1,
            },
            blocking=True,
        )

    assert error.value.translation_key == "pot_account_mismatch"
    assert error.value.translation_placeholders == {
        "account_name": "Joint Account",
        "pot_name": "Savings",
        "pot_account_name": "Current Account",
    }


async def test_transfer_requires_admin(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    monzo: AsyncMock,
    transfer_devices: TransferDevices,
) -> None:
    """Test pot transfers require administrator access."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DEPOSIT_INTO_POT,
            {
                ATTR_ACCOUNT: transfer_devices.account_device_id,
                ATTR_POT: transfer_devices.pot_device_id,
                ATTR_AMOUNT: 1,
            },
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    monzo.user_account.pot_deposit.assert_not_awaited()


async def test_api_error(
    hass: HomeAssistant,
    monzo: AsyncMock,
    transfer_devices: TransferDevices,
) -> None:
    """Test a Monzo API error is exposed as a Home Assistant error."""
    monzo.user_account.pot_deposit.side_effect = InvalidMonzoAPIResponseError

    with pytest.raises(HomeAssistantError) as error:
        await _async_call_transfer(hass, transfer_devices, SERVICE_DEPOSIT_INTO_POT, 1)

    assert error.value.translation_key == "transfer_status_unknown"
    assert monzo.user_account.accounts.await_count == 1
    assert monzo.user_account.pots.await_count == 1


@pytest.mark.parametrize(
    "api_error",
    [
        pytest.param(ClientError(), id="client-error"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_transport_error(
    hass: HomeAssistant,
    monzo: AsyncMock,
    transfer_devices: TransferDevices,
    api_error: Exception,
) -> None:
    """Test a transport error is exposed as a Home Assistant error."""
    monzo.user_account.pot_deposit.side_effect = api_error

    with pytest.raises(HomeAssistantError) as error:
        await _async_call_transfer(hass, transfer_devices, SERVICE_DEPOSIT_INTO_POT, 1)

    assert error.value.translation_key == "transfer_status_unknown"
    assert monzo.user_account.accounts.await_count == 1
    assert monzo.user_account.pots.await_count == 1


async def test_false_transfer_result_is_failure(
    hass: HomeAssistant,
    monzo: AsyncMock,
    transfer_devices: TransferDevices,
) -> None:
    """Test a false transfer result is exposed as a Home Assistant error."""
    monzo.user_account.pot_deposit.return_value = False

    with pytest.raises(HomeAssistantError) as error:
        await _async_call_transfer(hass, transfer_devices, SERVICE_DEPOSIT_INTO_POT, 1)

    assert error.value.translation_key == "transfer_failed"
    assert monzo.user_account.accounts.await_count == 1
    assert monzo.user_account.pots.await_count == 1


async def test_api_rejection_details(
    hass: HomeAssistant,
    monzo: AsyncMock,
    transfer_devices: TransferDevices,
) -> None:
    """Test rejection details supplied by Monzo are exposed to the user."""
    monzo.user_account.pot_deposit.side_effect = InvalidMonzoAPIResponseError(
        {
            "code": "bad_request.unsupported_account",
            "message": "This account does not support pot transfers",
        }
    )

    with pytest.raises(HomeAssistantError) as error:
        await _async_call_transfer(hass, transfer_devices, SERVICE_DEPOSIT_INTO_POT, 1)

    assert error.value.translation_key == "transfer_rejected"
    assert error.value.translation_placeholders == {
        "account_name": "Current Account",
        "account_type": "uk_retail",
        "reason": (
            "bad_request.unsupported_account: "
            "This account does not support pot transfers"
        ),
    }


@pytest.mark.parametrize(
    "api_error",
    [
        pytest.param(AuthorisationExpiredError, id="monzo-authorisation-expired"),
        pytest.param(
            OAuth2TokenRequestReauthError(request_info=Mock(), domain=DOMAIN),
            id="oauth-refresh-rejected",
        ),
    ],
)
async def test_expired_authorisation_starts_reauthentication(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
    transfer_devices: TransferDevices,
    api_error: Exception | type[Exception],
) -> None:
    """Test expired Monzo authorization starts reauthentication."""
    monzo.user_account.pot_deposit.side_effect = api_error

    with (
        patch.object(polling_config_entry, "async_start_reauth") as start_reauth,
        pytest.raises(HomeAssistantError),
    ):
        await _async_call_transfer(hass, transfer_devices, SERVICE_DEPOSIT_INTO_POT, 1)

    start_reauth.assert_called_once_with(hass)
