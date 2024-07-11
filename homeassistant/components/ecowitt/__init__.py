"""The Ecowitt Weather Station Component."""

from __future__ import annotations

from aioecowitt import EcoWittListener
from aiohttp import web

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

type EcowittConfigEntry = ConfigEntry[EcoWittListener]


async def async_setup_entry(hass: HomeAssistant, entry: EcowittConfigEntry) -> bool:
    """Set up the Ecowitt component from UI."""
    ecowitt = entry.runtime_data = EcoWittListener()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle webhook callback."""
        return await ecowitt.handler(request)

    webhook.async_register(
        hass, DOMAIN, entry.title, entry.data[CONF_WEBHOOK_ID], handle_webhook
    )

    @callback
    def _stop_ecowitt(_: Event) -> None:
        """Stop the Ecowitt listener."""
        webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_ecowitt)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcowittConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
