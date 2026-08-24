"""Actions for the Monzo integration."""

from collections.abc import Awaitable, Callable
from decimal import Decimal, DecimalException
from typing import Any, Final, cast

from aiohttp import ClientError
from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestReauthError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr, selector, service

from .const import (
    DEVICE_MODEL_ACCOUNT,
    DEVICE_MODEL_POT,
    DOMAIN,
    NON_TRANSFER_ACCOUNT_TYPES,
)
from .coordinator import MonzoConfigEntry, MonzoCoordinator

ATTR_ACCOUNT: Final = "account"
ATTR_AMOUNT: Final = "amount"
ATTR_POT: Final = "pot"

SERVICE_DEPOSIT_INTO_POT: Final = "deposit_into_pot"
SERVICE_WITHDRAW_FROM_POT: Final = "withdraw_from_pot"

type TransferFunction = Callable[[str, str, int], Awaitable[bool]]


def _amount_to_minor_units(value: Any) -> int:
    """Validate an amount and convert it to minor currency units."""
    try:
        amount = Decimal(str(value))
        minor_units = amount * 100
    except (DecimalException, ValueError) as err:
        raise vol.Invalid("Amount must be a number") from err

    if (
        not amount.is_finite()
        or amount <= 0
        or minor_units <= 0
        or minor_units != minor_units.to_integral_value()
    ):
        raise vol.Invalid("Amount must be positive with no more than 2 decimal places")

    return int(minor_units)


def _transfer_rejection_reason(error: InvalidMonzoAPIResponseError) -> str | None:
    """Return the rejection details supplied by Monzo."""
    if not error.response or not isinstance(
        message := error.response.get("message"), str
    ):
        return None
    if isinstance(code := error.response.get("code"), str):
        return f"{code}: {message}"
    return message


TRANSFER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ACCOUNT): selector.DeviceSelector(
            {
                "filter": {
                    "integration": DOMAIN,
                    "model": DEVICE_MODEL_ACCOUNT,
                }
            }
        ),
        vol.Required(ATTR_POT): selector.DeviceSelector(
            {
                "filter": {
                    "integration": DOMAIN,
                    "model": DEVICE_MODEL_POT,
                }
            }
        ),
        vol.Required(ATTR_AMOUNT): _amount_to_minor_units,
    }
)


@callback
def _async_get_device(call: ServiceCall, field: str) -> dr.AnyDeviceEntry:
    """Get a selected device."""
    if (device := dr.async_get(call.hass).async_get(call.data[field])) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device",
        )
    return device


@callback
def _async_get_resource_id(device: dr.AnyDeviceEntry) -> str:
    """Get the Monzo resource ID represented by a device."""
    for domain, resource_id in device.identifiers:
        if domain == DOMAIN:
            return resource_id
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
    )


def _device_name(device: dr.AnyDeviceEntry) -> str:
    """Return the best available name for a device."""
    return device.name_by_user or device.name or device.id


@callback
def _async_resolve_transfer(
    call: ServiceCall,
) -> tuple[MonzoCoordinator, str, str]:
    """Resolve and validate the account and pot selected for a transfer."""
    account_device = _async_get_device(call, ATTR_ACCOUNT)
    pot_device = _async_get_device(call, ATTR_POT)
    account_id = _async_get_resource_id(account_device)
    pot_id = _async_get_resource_id(pot_device)

    for entry_id in account_device.config_entries & pot_device.config_entries:
        config_entry = call.hass.config_entries.async_get_entry(entry_id)
        if config_entry is None or config_entry.domain != DOMAIN:
            continue

        entry = cast(
            MonzoConfigEntry,
            service.async_get_config_entry(call.hass, DOMAIN, entry_id),
        )
        coordinator = entry.runtime_data.coordinator
        if (account := coordinator.data.accounts.get(account_id)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=(
                    "pot_selected_as_account"
                    if account_id in coordinator.data.pots
                    else "invalid_account"
                ),
                translation_placeholders={"device_name": _device_name(account_device)},
            )
        if account["type"] in NON_TRANSFER_ACCOUNT_TYPES:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_transfer_account",
                translation_placeholders={"device_name": _device_name(account_device)},
            )
        if (pot := coordinator.data.pots.get(pot_id)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=(
                    "account_selected_as_pot"
                    if pot_id in coordinator.data.accounts
                    else "invalid_pot"
                ),
                translation_placeholders={"device_name": _device_name(pot_device)},
            )
        if pot["current_account_id"] != account_id:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="pot_account_mismatch",
                translation_placeholders={
                    "account_name": account["name"],
                    "pot_name": pot["name"],
                    "pot_account_name": coordinator.data.accounts[
                        pot["current_account_id"]
                    ]["name"],
                },
            )
        return coordinator, account_id, pot_id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="different_entries",
    )


async def _async_transfer(
    call: ServiceCall,
    transfer_fn: Callable[[MonzoCoordinator], TransferFunction],
) -> None:
    """Transfer money between a Monzo account and pot."""
    coordinator, account_id, pot_id = _async_resolve_transfer(call)

    try:
        transfer_succeeded = await transfer_fn(coordinator)(
            account_id, pot_id, call.data[ATTR_AMOUNT]
        )
    except (AuthorisationExpiredError, OAuth2TokenRequestReauthError) as err:
        coordinator.config_entry.async_start_reauth(call.hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="authentication_expired",
        ) from err
    except InvalidMonzoAPIResponseError as err:
        if reason := _transfer_rejection_reason(err):
            account = coordinator.data.accounts[account_id]
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="transfer_rejected",
                translation_placeholders={
                    "account_name": account["name"],
                    "account_type": account["type"],
                    "reason": reason,
                },
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="transfer_status_unknown",
        ) from err
    except (ClientError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="transfer_status_unknown",
        ) from err

    if not transfer_succeeded:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="transfer_failed",
        )

    await coordinator.async_request_refresh()


async def _async_deposit_into_pot(call: ServiceCall) -> None:
    """Deposit money from an account into a pot."""
    await _async_transfer(
        call, lambda coordinator: coordinator.api.user_account.pot_deposit
    )


async def _async_withdraw_from_pot(call: ServiceCall) -> None:
    """Withdraw money from a pot into an account."""
    await _async_transfer(
        call, lambda coordinator: coordinator.api.user_account.pot_withdraw
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Monzo actions."""
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_DEPOSIT_INTO_POT,
        _async_deposit_into_pot,
        TRANSFER_SCHEMA,
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_WITHDRAW_FROM_POT,
        _async_withdraw_from_pot,
        TRANSFER_SCHEMA,
    )
