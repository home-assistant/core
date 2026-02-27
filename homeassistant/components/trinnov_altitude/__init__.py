"""The Trinnov Altitude integration."""

from __future__ import annotations

from trinnov_altitude.client import TrinnovAltitudeClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .const import CLIENT_ID, DOMAIN

PLATFORMS: list[str] = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.REMOTE,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for Trinnov Altitude."""

    host = entry.data[CONF_HOST].strip()
    mac = entry.data.get(CONF_MAC, "").strip() or None
    device = TrinnovAltitudeClient(host=host, mac=mac, client_id=CLIENT_ID)
    device.state.id = entry.unique_id

    await device.start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device

    async def stop(_event: Event) -> None:
        await device.stop()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Trinnov Altitude config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        client = hass.data[DOMAIN].pop(entry.entry_id)
        await client.stop()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
