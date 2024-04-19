"""The Monzo integration."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_AUTHENTICATION, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    device_registry as dr,
)
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AsyncConfigEntryAuth
from .const import (
    ACCOUNTS,
    ATTR_AMOUNT,
    CONF_COORDINATOR,
    DEFAULT_AMOUNT,
    DEPOSIT,
    DOMAIN,
    MODEL_POT,
    POTS,
    SERVICE_POT_TRANSFER,
    TRANSFER_ACCOUNTS,
    TRANSFER_TYPE,
    VALID_POT_TRANSFER_ACCOUNTS,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Monzo from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    async def async_get_monzo_api_data() -> dict[str, Any]:
        accounts = await externalapi.user_account.accounts()
        pots = await externalapi.user_account.pots()
        hass.data[DOMAIN][entry.entry_id][ACCOUNTS] = accounts
        hass.data[DOMAIN][entry.entry_id][POTS] = pots
        return {ACCOUNTS: accounts, POTS: pots}

    @callback
    async def handle_pot_transfer(call: ServiceCall) -> None:
        device_registry = dr.async_get(hass)
        amount = int(call.data.get(ATTR_AMOUNT, DEFAULT_AMOUNT) * 100)
        transfer_func: Callable[[str, str, int], Awaitable[bool]] = (
            externalapi.user_account.pot_deposit
            if call.data[TRANSFER_TYPE] == DEPOSIT
            else externalapi.user_account.pot_withdraw
        )

        try:
            account_ids, pot_ids = await _get_transfer_ids(
                call, device_registry, hass, entry
            )
        except ValueError:
            return

        success = all(
            await asyncio.gather(
                *[
                    transfer_func(account, pot, amount)
                    for account in account_ids
                    for pot in pot_ids
                ]
            )
        )

        if not success:
            _LOGGER.error(
                "External error handling pot transfer: one or more transactions failed"
            )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    externalapi = AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    coordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_monzo_api_data,
        update_interval=timedelta(minutes=1),
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_AUTHENTICATION: externalapi,
        CONF_COORDINATOR: coordinator,
    }

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.services.async_register(DOMAIN, SERVICE_POT_TRANSFER, handle_pot_transfer)

    return True


async def _get_transfer_ids(
    call: ServiceCall,
    device_registry: DeviceRegistry,
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> tuple[list[str], list[str]]:
    account_ids = await _get_selected_or_current_account_ids(
        call, device_registry, hass, entry
    )
    pot_ids = await asyncio.gather(
        *[
            _get_pot_id(device_registry, acc)
            for acc in call.data.get(ATTR_DEVICE_ID, "")
        ]
    )

    return account_ids, pot_ids


async def _get_selected_or_current_account_ids(
    call: ServiceCall,
    device_registry: DeviceRegistry,
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> list[str]:
    return (
        [
            acc["id"]
            for acc in hass.data[DOMAIN][entry.entry_id][ACCOUNTS]
            if acc["type"] == "uk_retail"
        ]
        if TRANSFER_ACCOUNTS not in call.data
        else await asyncio.gather(
            *[
                _get_transfer_account_id(device_registry, acc)
                for acc in call.data[TRANSFER_ACCOUNTS]
            ]
        )
    )


async def _get_transfer_account_id(
    device_registry: DeviceRegistry, device_id: str
) -> str:
    device = await _get_device(device_registry, device_id)
    if device.model not in VALID_POT_TRANSFER_ACCOUNTS:
        _LOGGER.error(
            "Pot deposit failed: Can't transfer between a pot and %s", device.name
        )
        raise ValueError
    _, account_id = next(iter(device.identifiers))
    return account_id


async def _get_pot_id(device_registry: DeviceRegistry, device_id: str) -> str:
    device = await _get_device(device_registry, device_id)
    if device.model != MODEL_POT:
        _LOGGER.error("Pot transfer failed: %s is not a pot", device.name)
        raise ValueError
    _, pot_id = next(iter(device.identifiers))
    return pot_id


async def _get_device(device_registry: DeviceRegistry, device_id: str) -> DeviceEntry:
    device = device_registry.async_get(device_id)
    if not device:
        _LOGGER.error("Pot deposit failed: Couldn't find device with id %s", device_id)
        raise ValueError
    return device


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN]

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in data:
        data.pop(entry.entry_id)

    return unload_ok
