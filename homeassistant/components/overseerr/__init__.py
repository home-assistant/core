"""The Overseerr integration."""

from __future__ import annotations

import json
from typing import cast

from aiohttp.hdrs import METH_POST
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from python_overseerr import OverseerrConnectionError

from homeassistant.components import cloud
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
CONF_CLOUDHOOK_URL = "cloudhook_url"

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


async def async_remove_entry(hass: HomeAssistant, entry: OverseerrConfigEntry) -> None:
    """Cleanup when entry is removed."""
    if cloud.async_active_subscription(hass):
        try:
            LOGGER.debug(
                "Removing Overseerr cloudhook (%s)", entry.data[CONF_WEBHOOK_ID]
            )
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass


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
        if CONF_CLOUDHOOK_URL in self.entry.data:
            res.append(self.entry.data[CONF_CLOUDHOOK_URL])
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
            self.entry.runtime_data.push = True
            return
        for url in self.webhook_urls:
            if await self.test_and_set_webhook(url):
                return
        LOGGER.info("Failed to register Overseerr webhook")
        if cloud.async_active_subscription(self.hass):
            LOGGER.info("Trying to register a cloudhook URL")
            url = await _async_cloudhook_generate_url(self.hass, self.entry)
            if await self.test_and_set_webhook(url):
                return
            LOGGER.error("Failed to register Overseerr cloudhook")

    async def check_need_change(self) -> bool:
        """Check if webhook needs to be changed."""
        current_config = await self.client.get_webhook_notification_config()
        return (
            not current_config.enabled
            or current_config.options.webhook_url not in self.webhook_urls
            or current_config.options.json_payload != json.loads(JSON_PAYLOAD)
            or current_config.types != REGISTERED_NOTIFICATIONS
        )

    async def test_and_set_webhook(self, url: str) -> bool:
        """Test and set webhook."""
        if await self.client.test_webhook_notification_config(url, JSON_PAYLOAD):
            LOGGER.debug("Setting Overseerr webhook to %s", url)
            await self.client.set_webhook_notification_config(
                enabled=True,
                types=REGISTERED_NOTIFICATIONS,
                webhook_url=url,
                json_payload=JSON_PAYLOAD,
            )
            self.entry.runtime_data.push = True
            return True
        return False

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


async def _async_cloudhook_generate_url(
    hass: HomeAssistant, entry: OverseerrConfigEntry
) -> str:
    """Generate the full URL for a webhook_id."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        webhook_id = entry.data[CONF_WEBHOOK_ID]
        webhook_url = await cloud.async_create_cloudhook(hass, webhook_id)
        data = {**entry.data, CONF_CLOUDHOOK_URL: webhook_url}
        hass.config_entries.async_update_entry(entry, data=data)
        return webhook_url
    return cast(str, entry.data[CONF_CLOUDHOOK_URL])
