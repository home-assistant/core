"""The Trinnov Altitude integration."""

from __future__ import annotations

from trinnov_altitude.exceptions import ConnectionFailedError, ConnectionTimeoutError
from trinnov_altitude.trinnov_altitude import TrinnovAltitude

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS: list[str] = [Platform.REMOTE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for Trinnov Altitude."""

    host = entry.data[CONF_HOST]
    client = TrinnovAltitude(host=host)

    try:
        await client.connect()
    except (ConnectionFailedError, ConnectionTimeoutError) as err:
        await client.disconnect()
        raise ConfigEntryNotReady(f"Unable to connect to {host}: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    async def disconnect(event: Event) -> None:
        await client.disconnect()

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
