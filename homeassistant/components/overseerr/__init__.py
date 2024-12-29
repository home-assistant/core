"""The Overseerr integration."""

from __future__ import annotations

import json

from aiohttp.hdrs import METH_POST
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from homeassistant.components.webhook import async_generate_url, async_register
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import HomeAssistantView

from .const import DOMAIN, JSON_PAYLOAD, LOGGER, REGISTERED_NOTIFICATIONS
from .coordinator import OverseerrConfigEntry, OverseerrCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OverseerrConfigEntry) -> bool:
    """Set up Overseerr from a config entry."""

    coordinator = OverseerrCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    webhook_manager = OverseerrWebhookManager(hass, entry)

    await webhook_manager.register_webhook()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OverseerrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class OverseerrWebhookManager:
    """Overseerr webhook manager."""

    def __init__(self, hass: HomeAssistant, entry: OverseerrConfigEntry) -> None:
        """Initialize Overseerr webhook manager."""
        self.hass = hass
        self.entry = entry
        self.client = entry.runtime_data.client

    async def register_webhook(self) -> None:
        """Register webhook."""
        if not await self.check_need_change():
            return
        async_register(
            self.hass,
            DOMAIN,
            self.entry.title,
            self.entry.data[CONF_WEBHOOK_ID],
            self.handle_webhook,
            allowed_methods=[METH_POST],
        )
        url = async_generate_url(self.hass, self.entry.data[CONF_WEBHOOK_ID])
        LOGGER.warning("Setting Overseerr webhook to %s", url)
        if not await self.client.test_webhook_notification_config(url, JSON_PAYLOAD):
            LOGGER.error("Failed to set Overseerr webhook")
            return
        await self.client.set_webhook_notification_config(
            enabled=True,
            types=REGISTERED_NOTIFICATIONS,
            webhook_url=url,
            json_payload=JSON_PAYLOAD,
        )

    async def check_need_change(self) -> bool:
        """Check if webhook needs to be changed."""
        current_config = await self.client.get_webhook_notification_config()
        url = async_generate_url(self.hass, self.entry.data[CONF_WEBHOOK_ID])
        return (
            not current_config.enabled
            or current_config.options.webhook_url != url
            or current_config.options.json_payload != json.loads(JSON_PAYLOAD)
            or current_config.types != REGISTERED_NOTIFICATIONS
        )

    async def handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response:
        """Handle webhook."""
        data = await request.json()
        LOGGER.debug("Received webhook payload: %s", data)
        if data["notification_type"].startswith("MEDIA"):
            await self.entry.runtime_data.async_refresh()
        return HomeAssistantView.json({"message": "ok"})
