"""The Trinnov Altitude integration."""

from __future__ import annotations

from trinnov_altitude.client import TrinnovAltitudeClient
from trinnov_altitude.exceptions import ConnectionFailedError, ConnectionTimeoutError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CLIENT_ID

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for Trinnov Altitude."""

    host_value = entry.data.get(CONF_HOST, "")
    if isinstance(host_value, str):
        host = host_value.strip()
    else:
        host = str(host_value)

    mac_value = entry.data.get(CONF_MAC)
    if isinstance(mac_value, str):
        mac = mac_value.strip() or None
    else:
        mac = None

    device = TrinnovAltitudeClient(host=host, mac=mac, client_id=CLIENT_ID)

    try:
        await device.start()
        await device.wait_synced()
    except (ConnectionFailedError, ConnectionTimeoutError, TimeoutError) as err:
        await device.stop()
        raise ConfigEntryNotReady(
            f"Could not connect to Trinnov Altitude at {host}"
        ) from err

    entry.runtime_data = device

    async def stop(_event: Event) -> None:
        await device.stop()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Trinnov Altitude config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.stop()

    return unload_ok
