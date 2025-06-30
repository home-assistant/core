"""The CCL Electronics integration."""

from __future__ import annotations

import logging
from typing import Any

from aioccl import CCLDevice, CCLServer
from aioccl.exception import CCLDeviceRegistrationException
from aiohttp import web
from aiohttp.hdrs import METH_POST

from homeassistant.components import webhook
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, NAME
from .coordinator import CCLConfigEntry, CCLCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CCLConfigEntry) -> bool:
    """Set up a config entry for a single CCL device."""
    if hasattr(entry, "runtime_data"):
        assert isinstance(entry.runtime_data, CCLCoordinator)
        _LOGGER.debug(
            "Retrying connecting to device with webhook ID %s",
            entry.data[CONF_WEBHOOK_ID],
        )
        device = entry.runtime_data.device
        coordinator = entry.runtime_data

    else:
        device = CCLDevice(entry.data[CONF_WEBHOOK_ID])
        coordinator = entry.runtime_data = CCLCoordinator(hass, device, entry)

        async def register_webhook() -> None:
            """Register webhook for the device."""

            def handle_webhook(
                hass: HomeAssistant, webhook_id: str, request: web.Request
            ) -> Any:
                """Handle incoming requests from CCL devices."""
                return CCLServer.handler(request)

            webhook_url = webhook.async_generate_url(
                hass,
                entry.data[CONF_WEBHOOK_ID],
                allow_external=False,
                allow_ip=True,
            )

            webhook_name = "CCL Electronics"
            if entry.title != NAME:
                webhook_name = f"{NAME} {entry.title}"

            webhook.async_register(
                hass,
                DOMAIN,
                webhook_name,
                entry.data[CONF_WEBHOOK_ID],
                handle_webhook,
                allowed_methods=[METH_POST],
            )
            _LOGGER.debug("Webhook registered at hass: %s", webhook_url)

        async def unregister_webhook(_: Any) -> None:
            webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
        )

        entry.async_create_background_task(
            hass, register_webhook(), "ccl_register_webhook"
        )
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    try:
        CCLServer.register(device)
    except CCLDeviceRegistrationException:
        _LOGGER.debug(
            "Device with webhook ID %s is already registered",
            CONF_WEBHOOK_ID,
        )

    @callback
    def push_update_callback(data) -> None:
        """Handle data pushed from the device."""
        coordinator.async_set_updated_data(data)

    device.set_update_callback(push_update_callback)

    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CCLConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    CCLServer.devices.pop(entry.data[CONF_WEBHOOK_ID], None)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
