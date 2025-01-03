"""The Monzo integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any

from aiohttp.web import Request
from monzopy import InvalidMonzoAPIResponseError

from homeassistant.components import cloud
from homeassistant.components.webhook import (
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .api import AuthenticatedMonzoAPI
from .const import DOMAIN, EVENT_TRANSACTION_CREATED, MONZO_EVENT
from .coordinator import MonzoCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_WEBHOOK_IDS = "webhook_ids"
WEBHOOK_ACTIVATION = "webhook_activation"
WEBHOOK_DEACTIVATION = "webhook_deactivation"
WEBHOOK_PUSH_TYPE = "push_type"
CLOUDHOOK_HOST = "hooks.nabu.casa"

PLATFORMS: list[Platform] = [Platform.SENSOR]
type MonzoConfigEntry = ConfigEntry[MonzoData]


@dataclass
class MonzoData:
    """Runtime data stored in the MonzoConfigEntry."""

    coordinator: MonzoCoordinator
    webhook_ids: set[str] = field(default_factory=set)
    cloudhook_urls: set[str] = field(default_factory=set)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Monzo from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)

    external_api = AuthenticatedMonzoAPI(async_get_clientsession(hass), session)

    coordinator = MonzoCoordinator(hass, external_api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = MonzoData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    webhook_manager = MonzoWebhookManager(hass, entry)

    async def manage_cloudhook(state: cloud.CloudConnectionState) -> None:
        if state is cloud.CloudConnectionState.CLOUD_CONNECTED:
            await webhook_manager.register_webhooks(None)

        if state is cloud.CloudConnectionState.CLOUD_DISCONNECTED:
            await webhook_manager.unregister_webhooks()
            async_call_later(hass, 30, webhook_manager.register_webhooks)

    if cloud.async_active_subscription(hass):
        if cloud.async_is_connected(hass):
            await webhook_manager.register_webhooks(None)
        cloud.async_listen_connection_change(hass, manage_cloudhook)
    elif hass.state == CoreState.running:
        await webhook_manager.register_webhooks(None)
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, webhook_manager.register_webhooks
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class MonzoWebhookManager:
    """Manages Monzo webhooks."""

    _register_lock = asyncio.Lock()

    def __init__(self, hass: HomeAssistant, entry: MonzoConfigEntry) -> None:
        """Initialise the webhook manager."""
        self.hass = hass
        self.entry = entry

    async def register_webhooks(self, _: Any) -> None:
        """Register webhooks for all Monzo accounts."""
        async with self._register_lock:
            coordinator: MonzoCoordinator = self.entry.runtime_data.coordinator
            await self.unregister_old_webhooks(coordinator)
            for account in await coordinator.api.user_account.accounts():
                webhook_id = self.entry.entry_id + account["id"]
                self.entry.runtime_data.webhook_ids.add(webhook_id)

                if cloud.async_active_subscription(self.hass):
                    webhook_url = await self._async_cloudhook_generate_url(webhook_id)
                else:
                    webhook_url = webhook_generate_url(self.hass, webhook_id)

                if not webhook_url.startswith("https://"):
                    _LOGGER.warning(
                        "Webhook not registered - "
                        "https and port 443 is required to register the webhook"
                    )
                    return

                webhook_register(
                    self.hass,
                    DOMAIN,
                    "Monzo",
                    webhook_id,
                    async_handle_webhook,
                )

                try:
                    await coordinator.api.user_account.register_webhooks(webhook_url)
                    _LOGGER.info("Registered Monzo webhook: %s", webhook_url)
                except InvalidMonzoAPIResponseError:
                    _LOGGER.error("Error during webhook registration")
                else:
                    self.entry.async_on_unload(self.unregister_webhooks)

    async def unregister_old_webhooks(self, coordinator: MonzoCoordinator) -> None:
        """Unregister any old webhooks associated with this client."""
        await coordinator.api.user_account.unregister_webhooks()

    async def _async_cloudhook_generate_url(self, webhook_id: str) -> str:
        """Generate the full URL for a webhook_id."""
        webhook_url = await cloud.async_create_cloudhook(self.hass, webhook_id)
        self.entry.runtime_data.cloudhook_urls.add(webhook_url)
        return webhook_url

    async def unregister_webhooks(self) -> None:
        """Unregister all Monzo webooks."""
        coordinator: MonzoCoordinator = self.entry.runtime_data.coordinator

        async_dispatcher_send(
            self.hass,
            f"signal-{DOMAIN}-webhook-None",
            {"type": "None", "data": {WEBHOOK_PUSH_TYPE: WEBHOOK_DEACTIVATION}},
        )
        while self.entry.runtime_data.webhook_ids:
            webhook_id = self.entry.runtime_data.webhook_ids.pop()
            _LOGGER.debug("Unregister Monzo webhook (%s)", webhook_id)
            webhook_unregister(self.hass, webhook_id)

            if cloud.async_active_subscription(self.hass):
                try:
                    _LOGGER.debug("Removing Monzo cloudhook (%s)", webhook_id)
                    await cloud.async_delete_cloudhook(self.hass, webhook_id)
                except cloud.CloudNotAvailable:
                    _LOGGER.error(
                        "Failed to remove Monzo cloudhook (%s) - cloud unavailable",
                        webhook_id,
                    )
        await self.unregister_old_webhooks(coordinator)


async def async_handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> None:
    """Handle webhook callback."""
    try:
        data = await request.json()
    except ValueError as err:
        _LOGGER.error("Error in data: %s", err)
        return

    _LOGGER.debug("Got webhook data: %s", data)

    event_type = data.get("type")

    if event_type == EVENT_TRANSACTION_CREATED:
        async_send_event(hass, event_type, data.get("data"))
    else:
        _LOGGER.debug("Got unexpected event type from webhook: %s", event_type)


def async_send_event(hass: HomeAssistant, event_type: str, data: dict) -> None:
    """Send events."""
    _LOGGER.debug("%s: %s", event_type, data)
    if data and "account_id" in data:
        async_dispatcher_send(
            hass,
            monzo_event_signal(event_type, data["account_id"]),
            {"data": data},
        )
    else:
        _LOGGER.error("Webhook data malformed: %s", data)


def monzo_event_signal(event_type: str, account_id: str) -> str:
    """Generate a unique signal for a Monzo event."""
    return f"{MONZO_EVENT}_{event_type}_{account_id}"
