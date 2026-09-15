"""The EARN-E P1 Meter integration."""

from earn_e_p1 import DEFAULT_PORT, EarnEP1Listener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SERIAL, EARN_E_P1_DATA
from .coordinator import EarnEP1Coordinator
from .models import EarnEP1Data

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EarnEP1ConfigEntry = ConfigEntry[EarnEP1Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> bool:
    """Set up EARN-E P1 Meter from a config entry."""
    host = entry.data[CONF_HOST]
    serial = entry.data[CONF_SERIAL]
    mac = entry.data.get(CONF_MAC)

    if (data := hass.data.get(EARN_E_P1_DATA)) is None:
        listener = EarnEP1Listener()
        try:
            await listener.start()
        except OSError as err:
            raise ConfigEntryNotReady(
                f"Cannot start UDP listener on port {DEFAULT_PORT}: {err}"
            ) from err
        data = hass.data[EARN_E_P1_DATA] = EarnEP1Data(listener)

    # Claim the listener before the first await, so that another entry
    # unloading while this one sets up cannot stop it from under us.
    data.entries.add(entry.entry_id)

    async def _release_listener() -> None:
        """Stop the shared listener once the last entry has released it."""
        data.entries.discard(entry.entry_id)
        if not data.entries:
            del hass.data[EARN_E_P1_DATA]
            await data.listener.stop()

    entry.async_on_unload(_release_listener)

    coordinator = EarnEP1Coordinator(hass, entry, host, serial, data.listener, mac)
    coordinator.start()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.stop()

    return unload_ok
