"""The CCL Electronics integration."""

from __future__ import annotations

import logging
from typing import Any

from aioccl import CCLDevice, CCLServer
from aioccl.server import register
from aiohttp import web
from aiohttp.hdrs import METH_POST
from const import DOMAIN, NAME

from homeassistant.components import webhook
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant, callback

from .coordinator import CCLConfigEntry, CCLCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

devices: dict[str, CCLDevice] = {}


async def async_setup_entry(hass: HomeAssistant, entry: CCLConfigEntry) -> bool:
    """Set up a config entry for a single CCL device."""
    # Create the device and register a webhook after restart
    if entry.data[CONF_WEBHOOK_ID] not in devices:
        device = devices[entry.data[CONF_WEBHOOK_ID]] = CCLDevice(
            entry.data[CONF_WEBHOOK_ID]
        )

        coordinator = entry.runtime_data = CCLCoordinator(hass, device, entry)

        register(devices, device)

        async def register_webhook() -> None:
            """Register webhook for the device."""

            def handle_webhook(
                hass: HomeAssistant, webhook_id: str, request: web.Request
            ) -> Any:
                """Handle incoming requests from CCL devices."""
                return CCLServer.handler(request)

            try:
                webhook_url = webhook.async_generate_url(
                    hass,
                    entry.data[CONF_WEBHOOK_ID],
                    allow_ip=True,
                )

                webhook.async_register(
                    hass,
                    DOMAIN,
                    f"{NAME}-{entry.data[CONF_WEBHOOK_ID]}",
                    entry.data[CONF_WEBHOOK_ID],
                    handle_webhook,
                    allowed_methods=[METH_POST],
                )
                _LOGGER.debug("Webhook registered at hass: %s", webhook_url)

            except ValueError as err:
                _LOGGER.error("Failed to register webhook: %s", err)

        await register_webhook()

    else:
        device = devices[entry.data[CONF_WEBHOOK_ID]]

        coordinator = entry.runtime_data = CCLCoordinator(hass, device, entry)

    @callback
    def push_update_callback(data) -> None:
        """Handle data pushed from the device."""
        coordinator.async_set_updated_data(data)

    device.set_update_callback(push_update_callback)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CCLConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
