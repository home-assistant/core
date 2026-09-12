"""The CCL Electronics integration."""

import contextlib
import logging
from typing import Any

from aioccl import CCLDevice, CCLServer
from aiohttp import web
from aiohttp.hdrs import METH_POST

from homeassistant.components import webhook
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, NAME
from .coordinator import CCLConfigEntry, CCLCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


def register_webhook(hass: HomeAssistant, webhook_id: str, device: CCLDevice) -> None:
    """Register webhook for the device."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> Any:
        """Handle incoming requests from CCL devices."""
        return await CCLServer.handler(request, device)

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
    device = CCLDevice(webhook_id)

    coordinator = entry.runtime_data = CCLCoordinator(hass, device, entry)

    # Ensure any previously-registered webhook is removed
    with contextlib.suppress(ValueError):
        webhook.async_unregister(hass, webhook_id)

    try:
        register_webhook(hass, webhook_id, device)
    except ValueError as err:
        _LOGGER.error("Failed to register webhook: %s", err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_register_webhook",
            translation_placeholders={"error": str(err)},
        ) from err
    _LOGGER.debug("Webhook registered at hass: %s", webhook_id)

    @callback
    def push_update_callback(data: dict[str, Any]) -> None:
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
