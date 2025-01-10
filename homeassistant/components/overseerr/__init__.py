"""The Overseerr integration."""

from __future__ import annotations

import json

from aiohttp.hdrs import METH_POST
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from python_overseerr import OverseerrConnectionError

from homeassistant.components.webhook import (
    async_generate_url,
    async_register,
    async_unregister,
)
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_KEY, JSON_PAYLOAD, LOGGER, REGISTERED_NOTIFICATIONS
from .coordinator import OverseerrConfigEntry, OverseerrCoordinator
from .services import setup_services

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Overseerr component."""
    setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OverseerrConfigEntry) -> bool:
    """Set up Overseerr from a config entry."""

    coordinator = OverseerrCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    webhook_manager = OverseerrWebhookManager(hass, entry)

    try:
        await webhook_manager.register_webhook()
    except OverseerrConnectionError:
        LOGGER.error("Failed to register Overseerr webhook")

    entry.async_on_unload(webhook_manager.unregister_webhook)

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

    @property
    def webhook_urls(self) -> list[str]:
        """Return webhook URLs."""
        urls = [
            async_generate_url(
                self.hass, self.entry.data[CONF_WEBHOOK_ID], prefer_external=external
            )
            for external in (False, True)
        ]
        res = []
        for url in urls:
            if url not in res:
                res.append(url)
        return res

    async def register_webhook(self) -> None:
        """Register webhook."""
        async_register(
            self.hass,
            DOMAIN,
            self.entry.title,
            self.entry.data[CONF_WEBHOOK_ID],
            self.handle_webhook,
            allowed_methods=[METH_POST],
        )
        if not await self.check_need_change():
            return
        for url in self.webhook_urls:
            if await self.client.test_webhook_notification_config(url, JSON_PAYLOAD):
                LOGGER.debug("Setting Overseerr webhook to %s", url)
                await self.client.set_webhook_notification_config(
                    enabled=True,
                    types=REGISTERED_NOTIFICATIONS,
                    webhook_url=url,
                    json_payload=JSON_PAYLOAD,
                )
                return
        LOGGER.error("Failed to set Overseerr webhook")

    async def check_need_change(self) -> bool:
        """Check if webhook needs to be changed."""
        current_config = await self.client.get_webhook_notification_config()
        return (
            not current_config.enabled
            or current_config.options.webhook_url not in self.webhook_urls
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
        async_dispatcher_send(hass, EVENT_KEY, data)
        return HomeAssistantView.json({"message": "ok"})

    async def unregister_webhook(self) -> None:
        """Unregister webhook."""
        async_unregister(self.hass, self.entry.data[CONF_WEBHOOK_ID])
