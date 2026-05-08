"""The CCL Electronics integration."""

import logging
from typing import Any

from aioccl import CCLDevice, CCLServer
from aiohttp import web
from aiohttp.hdrs import METH_POST

from homeassistant.components import webhook
from homeassistant.components.http import NoURLAvailableError
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, NAME
from .coordinator import CCLConfigEntry, CCLCoordinator
from .devices import devices

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def register_webhook(hass: HomeAssistant, webhook_id: str) -> None:
    """Register webhook for the device."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> Any:
        """Handle incoming requests from CCL devices."""
        return await CCLServer.handler(request, devices)

    webhook.async_register(
        hass,
        DOMAIN,
        f"{NAME}-{webhook_id}",
        webhook_id,
        handle_webhook,
        allowed_methods=[METH_POST],
    )


async def async_setup_entry(hass: HomeAssistant, entry: CCLConfigEntry) -> bool:
    """Set up a config entry for a single CCL device."""
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    # Create the device and register a webhook after restart
    if webhook_id not in devices:
        device = devices[webhook_id] = CCLDevice(webhook_id)

        coordinator = entry.runtime_data = CCLCoordinator(hass, device, entry)

        devices[device.passkey] = device

        try:
            await register_webhook(hass, entry.data[CONF_WEBHOOK_ID])
        except (ValueError, NoURLAvailableError) as err:
            _LOGGER.error("Failed to register webhook: %s", err)
            raise ConfigEntryNotReady(f"Failed to register webhook: {err}") from err
        _LOGGER.debug("Webhook registered at hass: %s", webhook_id)

    else:
        device = devices[webhook_id]

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
    devices.pop(entry.data[CONF_WEBHOOK_ID], None)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
