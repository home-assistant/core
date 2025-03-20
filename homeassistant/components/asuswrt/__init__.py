"""Support for ASUSWRT devices."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .router import AsusWrtRouter

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR]

type AsusWrtConfigEntry = ConfigEntry[AsusWrtRouter]


async def async_setup_entry(hass: HomeAssistant, entry: AsusWrtConfigEntry) -> bool:
    """Set up AsusWrt platform."""

    router = AsusWrtRouter(hass, entry)
    await router.setup()

    router.async_on_close(entry.add_update_listener(update_listener))

    async def async_close_connection(event: Event) -> None:
        """Close AsusWrt connection on HA Stop."""
        await router.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    entry.runtime_data = router

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AsusWrtConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        router = entry.runtime_data
        await router.close()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: AsusWrtConfigEntry) -> None:
    """Update when config_entry options update."""
    router = entry.runtime_data

    if router.update_options(entry.options):
        await hass.config_entries.async_reload(entry.entry_id)
