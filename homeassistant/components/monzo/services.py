"""Register services for the Monzo integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry

from .api import AuthenticatedMonzoAPI
from .const import DOMAIN, MODEL_POT
from .coordinator import MonzoCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

SERVICE_POT_TRANSFER = "pot_transfer"


ATTR_AMOUNT = "amount"
DEFAULT_AMOUNT = 1
TRANSFER_TYPE = "transfer_type"
TRANSFER_TYPE_DEPOSIT = "deposit"
TRANSFER_TYPE_WITHDRAWAL = "withdraw"
TRANSFER_ACCOUNT = "transfer_account"
TRANSFER_POTS = "transfer_pots"

MODEL_CURRENT_ACCOUNT = "Current Account"
MODEL_JOINT_ACCOUNT = "Joint Account"
VALID_TRANSFER_ACCOUNTS = {MODEL_CURRENT_ACCOUNT, MODEL_JOINT_ACCOUNT}
VALID_POT_ACCOUNTS = {
    MODEL_POT,
}

ACCOUNT_ERROR = "Pot transfer failed: %s is not an account."
POT_ERROR = "Pot transfer failed: %s is not a pot."
NO_POT_ERROR = "Pot transfer failed: No valid pots."


async def register_services(hass: HomeAssistant) -> None:
    """Register services for the Monzo integration."""

    @callback
    async def handle_pot_transfer(call: ServiceCall) -> None:
        device_registry = dr.async_get(hass)
        first_pot = device_registry.async_get(call.data[TRANSFER_POTS][0])
        if first_pot is None:
            _LOGGER.error(NO_POT_ERROR)
            return
        entry_id = next(iter(first_pot.config_entries))
        amount = int(call.data.get(ATTR_AMOUNT, DEFAULT_AMOUNT) * 100)
        coordinator: MonzoCoordinator = hass.data[DOMAIN][entry_id]
        api = coordinator.api
        transfer_func: Callable[[str, str, int], Awaitable[bool]] = (
            api.user_account.pot_deposit
            if call.data[TRANSFER_TYPE] == TRANSFER_TYPE_DEPOSIT
            else api.user_account.pot_withdraw
        )

        try:
            account_id = await _get_account_id(call, api, device_registry)
            pot_ids = await _get_pot_ids(call, device_registry)
        except ValueError:
            return

        success = all(
            await asyncio.gather(
                *[transfer_func(account_id, pot, amount) for pot in pot_ids]
            )
        )

        if not success:
            _LOGGER.error(
                "External error handling pot transfer: one or more transactions failed"
            )

    hass.services.async_register(DOMAIN, SERVICE_POT_TRANSFER, handle_pot_transfer)


async def _get_account_id(
    call: ServiceCall, api: AuthenticatedMonzoAPI, device_registry: DeviceRegistry
) -> str:
    return (
        await _get_current_account_id(api)
        if TRANSFER_ACCOUNT not in call.data
        else await _get_account_id_from_device(
            device_registry,
            call.data[TRANSFER_ACCOUNT],
            VALID_TRANSFER_ACCOUNTS,
            ACCOUNT_ERROR,
        )
    )


async def _get_current_account_id(api: AuthenticatedMonzoAPI) -> str:
    curent_account_id: str = next(
        acc["id"]
        for acc in (await api.user_account.accounts())
        if acc["type"] == "uk_retail"
    )

    return curent_account_id


async def _get_account_id_from_device(
    device_registry: DeviceRegistry,
    device_id: str,
    valid_account_types: set[str],
    error_str: str,
) -> str:
    device = await _get_device(device_registry, device_id)
    _validate_account(valid_account_types, error_str, device)
    _, account_id = next(iter(device.identifiers))
    return account_id


def _validate_account(
    valid_account_types: set[str], error_str: str, device: DeviceEntry
) -> None:
    if device.model not in valid_account_types:
        _LOGGER.error(error_str, device.name)
        raise ValueError


async def _get_pot_ids(call: ServiceCall, device_registry: DeviceRegistry) -> list[str]:
    return await asyncio.gather(
        *[
            _get_account_id_from_device(
                device_registry, acc, VALID_POT_ACCOUNTS, POT_ERROR
            )
            for acc in call.data.get(TRANSFER_POTS, "")
        ]
    )


async def _get_device(device_registry: DeviceRegistry, device_id: str) -> DeviceEntry:
    device = device_registry.async_get(device_id)
    if not device:
        _LOGGER.error("Pot deposit failed: Couldn't find device with id %s", device_id)
        raise ValueError
    return device
