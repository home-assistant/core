"""The EARN-E P1 Meter integration."""

from earn_e_p1 import DEFAULT_PORT, EarnEP1Listener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SERIAL, DOMAIN, EARN_E_P1_DATA
from .coordinator import EarnEP1Coordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EarnEP1ConfigEntry = ConfigEntry[EarnEP1Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> bool:
    """Set up EARN-E P1 Meter from a config entry."""
    host = entry.data[CONF_HOST]
    serial = entry.data[CONF_SERIAL]
    mac = entry.data.get(CONF_MAC)

    # Get or create shared listener
    if (listener := hass.data.get(EARN_E_P1_DATA)) is None:
        listener = EarnEP1Listener()
        try:
            await listener.start()
        except OSError as err:
            raise ConfigEntryNotReady(
                f"Cannot start UDP listener on port {DEFAULT_PORT}: {err}"
            ) from err
        hass.data[EARN_E_P1_DATA] = listener

    coordinator = EarnEP1Coordinator(hass, entry, host, serial, listener, mac)
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
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            await hass.data.pop(EARN_E_P1_DATA).stop()

    return unload_ok
