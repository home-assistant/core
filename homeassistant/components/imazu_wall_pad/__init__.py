"""The Imazu Wall Pad integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant

from .const import DOMAIN, PLATFORMS
from .gateway import ImazuGateway


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Imazu Wall Pad from a config entry."""
    gateway = ImazuGateway(hass, entry)
    await gateway.async_load_entity_registry()

    if not await gateway.async_connect():
        await gateway.async_close()
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = gateway
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await gateway.async_close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        gateway = hass.data[DOMAIN].pop(entry.entry_id)
        await gateway.async_close()

    return unload_ok
