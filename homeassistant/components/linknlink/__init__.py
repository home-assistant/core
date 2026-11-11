"""The LinknLink integration."""

from aiolinknlink import UltraClient, UltraDevice

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, DISPLAY_MODEL
from .coordinator import LinknLinkConfigEntry, LinknLinkCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LinknLinkConfigEntry) -> None:
    """Set up LinknLink from a config entry."""
    assert entry.unique_id is not None
    device = UltraDevice(
        id=entry.unique_id,
        ip=entry.data[CONF_HOST],
        port=DEFAULT_PORT,
        mac=entry.unique_id,
        name=DISPLAY_MODEL,
        model=DISPLAY_MODEL,
    )
    client = UltraClient(default_port=DEFAULT_PORT)
    coordinator = LinknLinkCoordinator(hass, entry, client, device)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: LinknLinkConfigEntry) -> None:
    """Unload a LinknLink config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
