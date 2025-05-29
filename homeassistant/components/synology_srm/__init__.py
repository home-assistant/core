"""The Synology SRM component."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .device_tracker import SynologySRMConfigEntry, SynologySrmDeviceScanner, get_api

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: SynologySRMConfigEntry
) -> bool:
    """Set up the Synology SRM from a config entry."""
    api = get_api(dict(config_entry.data))
    scanner = SynologySrmDeviceScanner(hass, api, config_entry)
    await scanner.setup()

    async def async_close_connection(event: Event) -> None:
        """Close Synology SRM on HA Stop."""
        await scanner.close()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    config_entry.runtime_data = scanner

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: SynologySRMConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
