"""The CCL Electronics integration."""

import contextlib
import logging
import time
from typing import Any

from aioccl import CCLDevice, CCLServer
from aiohttp import web
from aiohttp.hdrs import METH_POST

from homeassistant.components import webhook
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, NAME
from .coordinator import CCLConfigEntry, CCLCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

KEY_DEVICES: HassKey[dict[str, CCLDevice]] = HassKey("ccl_devices")


async def register_webhook(hass: HomeAssistant, webhook_id: str) -> None:
    """Register webhook for the device."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> Any:
        """Handle incoming requests from CCL devices."""
        return await CCLServer.handler(request, hass.data[KEY_DEVICES])

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
    # Create the device and register a webhook after restart, or fetch the existing device if it was already created during the config flow
    device = hass.data.setdefault(KEY_DEVICES, {}).get(
        webhook_id, CCLDevice(webhook_id)
    )

    coordinator = entry.runtime_data = CCLCoordinator(hass, device, entry)

    try:
        await register_webhook(hass, entry.data[CONF_WEBHOOK_ID])
    except ValueError as err:
        _LOGGER.error("Failed to register webhook: %s", err)
        raise ConfigEntryNotReady(f"Failed to register webhook: {err}") from err
    _LOGGER.debug("Webhook registered at hass: %s", webhook_id)

    @callback
    def push_update_callback(data) -> None:
        """Handle data pushed from the device."""
        coordinator.async_set_updated_data(data)
        coordinator.last_update_time = time.monotonic()

    device.set_update_callback(push_update_callback)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CCLConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    with contextlib.suppress(KeyError):
        hass.data[KEY_DEVICES].pop(entry.data[CONF_WEBHOOK_ID], None)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
