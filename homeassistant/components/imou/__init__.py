"""Support for Imou devices."""

from pyimouapi.device import ImouDeviceManager
from pyimouapi.ha_device import ImouHaDeviceManager
from pyimouapi.openapi import ImouOpenApiClient

from homeassistant.core import HomeAssistant, callback

from .const import API_URLS, CONF_API_URL, CONF_APP_ID, CONF_APP_SECRET, PLATFORMS
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator, get_update_interval


async def async_setup_entry(hass: HomeAssistant, entry: ImouConfigEntry) -> bool:
    """Set up Imou integration from a config entry."""
    imou_client = ImouOpenApiClient(
        entry.data[CONF_APP_ID],
        entry.data[CONF_APP_SECRET],
        API_URLS[entry.data[CONF_API_URL]],
    )
    device_manager = ImouDeviceManager(imou_client)
    imou_device_manager = ImouHaDeviceManager(device_manager)
    imou_coordinator = ImouDataUpdateCoordinator(hass, imou_device_manager, entry)
    await imou_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = imou_coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # DataUpdateCoordinator schedules periodic refreshes only when it has
    # listeners. With zero entities (e.g. an empty account at setup), register a
    # no-op listener so polling continues and later devices are discovered via
    # new_device_callbacks.
    @callback
    def _async_keep_polling() -> None:
        """Keep periodic polling when no entities are registered yet."""

    entry.async_on_unload(imou_coordinator.async_add_listener(_async_keep_polling))
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: ImouConfigEntry) -> None:
    """Handle config entry options updates."""
    entry.runtime_data.update_interval = get_update_interval(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ImouConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
