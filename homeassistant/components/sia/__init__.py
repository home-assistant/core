"""The sia integration."""

from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .hub import SIAConfigEntry, SIAHub


async def async_setup_entry(hass: HomeAssistant, entry: SIAConfigEntry) -> bool:
    """Set up sia from a config entry."""
    hub = SIAHub(hass, entry)
    hub.async_setup_hub()

    try:
        if hub.sia_client:
            await hub.sia_client.async_start(reuse_port=True)
    except OSError as exc:
        raise ConfigEntryNotReady(
            f"SIA Server at port {entry.data[CONF_PORT]} could not start."
        ) from exc

    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SIAConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok
