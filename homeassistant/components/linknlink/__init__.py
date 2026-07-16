"""The LinknLink integration."""

from aiolinknlink import UltraClient, UltraDevice

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DEFAULT_PORT, DISPLAY_MODEL, DOMAIN, LEGACY_DISPLAY_MODEL
from .coordinator import LinknLinkConfigEntry, LinknLinkCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LinknLinkConfigEntry) -> bool:
    """Set up LinknLink from a config entry."""
    assert entry.unique_id is not None
    if entry.title == LEGACY_DISPLAY_MODEL:
        hass.config_entries.async_update_entry(entry, title=DISPLAY_MODEL)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    device = UltraDevice(
        id=entry.unique_id,
        ip=entry.data[CONF_HOST],
        port=port,
        mac=entry.data[CONF_MAC],
        name=DISPLAY_MODEL,
        model=DISPLAY_MODEL,
    )
    client = UltraClient(default_port=port)
    coordinator = LinknLinkCoordinator(hass, entry, client, device)

    await coordinator.async_config_entry_first_refresh()
    device.name = DISPLAY_MODEL
    device.model = DISPLAY_MODEL
    entry.runtime_data = coordinator

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
        identifiers={(DOMAIN, device.id)},
        manufacturer="LinknLink",
        model=device.model,
        name=device.name,
        serial_number=device.mac,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinknLinkConfigEntry) -> bool:
    """Unload a LinknLink config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
