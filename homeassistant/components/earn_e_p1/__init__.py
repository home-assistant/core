"""The EARN-E P1 Meter integration."""

from __future__ import annotations

from earn_e_p1 import DEFAULT_PORT, EarnEP1Listener
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import EarnEP1Coordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EarnEP1ConfigEntry = ConfigEntry[EarnEP1Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> bool:
    """Set up EARN-E P1 Meter from a config entry."""
    host = entry.data[CONF_HOST]
    serial = entry.data["serial"]

    # Get or create shared listener
    if DOMAIN not in hass.data:
        listener = EarnEP1Listener()
        try:
            await listener.start()
        except OSError as err:
            raise ConfigEntryNotReady(
                f"Cannot start UDP listener on port {DEFAULT_PORT}: {err}"
            ) from err
        hass.data[DOMAIN] = listener

    listener = hass.data[DOMAIN]
    coordinator = EarnEP1Coordinator(hass, entry, host, serial, listener)
    coordinator.start()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.stop()

        # Stop shared listener if no other entries are loaded
        other_loaded = any(
            e.state is ConfigEntryState.LOADED and e.entry_id != entry.entry_id
            for e in hass.config_entries.async_entries(DOMAIN)
        )
        if not other_loaded:
            await hass.data.pop(DOMAIN).stop()

    return unload_ok
