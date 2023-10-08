"""The Monzo integration."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components import cloud
from homeassistant.components.webhook import (
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_AUTHENTICATION,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CoreState, Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    device_registry as dr,
)
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AsyncConfigEntryAuth, InvalidMonzoAPIResponseError
from .const import (
    ACCOUNTS,
    ATTR_AMOUNT,
    CONF_CLOUDHOOK_URL,
    CONF_COORDINATOR,
    DEFAULT_AMOUNT,
    DEPOSIT,
    DOMAIN,
    MODEL_POT,
    POTS,
    SERVICE_POT_TRANSFER,
    SERVICE_REGISTER_WEBHOOK,
    SERVICE_UNREGISTER_WEBHOOK,
    TRANSFER_ACCOUNTS,
    TRANSFER_TYPE,
    VALID_POT_TRANSFER_ACCOUNTS,
    WEBHOOK_DEACTIVATION,
    WEBHOOK_PUSH_TYPE,
)
from .webhook import async_handle_webhook

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

    async def register_webhook(
        call_or_event_or_dt: ServiceCall | Event | datetime | None,
    ) -> None:
        for acc in hass.data[DOMAIN][entry.entry_id]["accounts"]:
            webhook_id = entry.entry_id + acc["id"]
            if (
                "webhooks_ids" not in entry.data
                or webhook_id not in hass.data[DOMAIN][entry.entry_id]["webhook_ids"]
            ):
                hass.data[DOMAIN][entry.entry_id]["webhook_ids"].append(webhook_id)

            if cloud.async_active_subscription(hass):
                webhook_url = await async_cloudhook_generate_url(
                    hass, entry, webhook_id
                )
            else:
                webhook_url = webhook_generate_url(hass, webhook_id)

            if not webhook_url.startswith("https://"):
                _LOGGER.warning(
                    "Webhook not registered - "
                    "https and port 443 is required to register the webhook"
                )
                return

            webhook_register(
                hass,
                DOMAIN,
                "Monzo",
                webhook_id,
                async_handle_webhook,
            )

            try:
                await externalapi.user_account.register_webhooks(webhook_url)
                _LOGGER.info("Register Monzo webhook: %s", webhook_url)
            except InvalidMonzoAPIResponseError:
                _LOGGER.error("Error during webhook registration")
            else:
                entry.async_on_unload(
                    hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_STOP, unregister_webhook
                    )
                )

    async def unregister_webhook(
        call_or_event_or_dt: ServiceCall | Event | datetime | None,
    ) -> None:
        if "webhook_ids" not in entry.data:
            return
        for webhook_id in hass.data[DOMAIN][entry.entry_id]["webhook_ids"]:
            _LOGGER.debug("Unregister Monzo webhook (%s)", webhook_id)
            async_dispatcher_send(
                hass,
                f"signal-{DOMAIN}-webhook-None",
                {"type": "None", "data": {WEBHOOK_PUSH_TYPE: WEBHOOK_DEACTIVATION}},
            )
            webhook_unregister(hass, webhook_id)
            try:
                await externalapi.user_account.unregister_webhooks()
            except InvalidMonzoAPIResponseError:
                _LOGGER.debug(
                    "No webhook to be dropped for %s",
                    webhook_id,
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
        "webhook_ids": [],
    }

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def manage_cloudhook(state: cloud.CloudConnectionState) -> None:
        if state is cloud.CloudConnectionState.CLOUD_CONNECTED:
            await register_webhook(None)

        if state is cloud.CloudConnectionState.CLOUD_DISCONNECTED:
            await unregister_webhook(None)
            async_call_later(hass, 30, register_webhook)

    if cloud.async_active_subscription(hass):
        if cloud.async_is_connected(hass):
            await register_webhook(None)
        cloud.async_listen_connection_change(hass, manage_cloudhook)

    elif hass.state == CoreState.running:
        await register_webhook(None)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, register_webhook)

    hass.services.async_register(DOMAIN, SERVICE_REGISTER_WEBHOOK, register_webhook)
    hass.services.async_register(DOMAIN, SERVICE_UNREGISTER_WEBHOOK, unregister_webhook)
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
            for acc in hass.data[DOMAIN][entry.entry_id + ACCOUNTS]
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

    if "webhook_ids" in entry.data:
        for webhook_id in hass.data[DOMAIN][entry.entry_id]["webhook_ids"]:
            webhook_unregister(hass, webhook_id)
            try:
                await data[entry.entry_id][CONF_AUTHENTICATION].unregister_webhooks()
            except InvalidMonzoAPIResponseError:
                _LOGGER.debug("No webhook to be dropped")
            _LOGGER.info("Unregister Monzo webhook")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in data:
        data.pop(entry.entry_id)

    return unload_ok


async def async_cloudhook_generate_url(
    hass: HomeAssistant, entry: ConfigEntry, webhook_id: str
) -> str:
    """Generate the full URL for a webhook_id."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        webhook_url = await cloud.async_create_cloudhook(hass, webhook_id)
        data = {**entry.data, CONF_CLOUDHOOK_URL: webhook_url}
        hass.config_entries.async_update_entry(entry, data=data)
        return webhook_url
    return str(entry.data[CONF_CLOUDHOOK_URL])
