"""The Trinnov Altitude integration."""

from __future__ import annotations

from trinnov_altitude.trinnov_altitude import TrinnovAltitude

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .const import CLIENT_ID, DOMAIN

PLATFORMS: list[str] = [Platform.REMOTE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for Trinnov Altitude."""

    host = entry.data[CONF_HOST].strip()
    mac = entry.data[CONF_MAC].strip()
    device = TrinnovAltitude(host=host, mac=mac, client_id=CLIENT_ID)

    # Spawn a task to start listening for events from the device
    device.start_listening()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device

    # If the device is connected, ensure that we disconnect when Home Assistant is stopped
    async def disconnect(event: Event) -> None:
        await device.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Trinnov Altitude config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        client = hass.data[DOMAIN].pop(entry.entry_id)
        await client.disconnect()

    return unload_ok
