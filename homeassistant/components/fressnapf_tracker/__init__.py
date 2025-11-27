"""The Fressnapf Tracker integration."""

from fressnapftracker import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TOKEN, CONF_SERIAL_NUMBER
from .coordinator import FressnapfTrackerDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

type FressnapfTrackerConfigEntry = ConfigEntry[
    dict[str, FressnapfTrackerDataUpdateCoordinator]
]


async def async_setup_entry(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> bool:
    """Set up Fressnapf Tracker from a config entry."""
    entry.runtime_data = {}

    for subentry in entry.subentries.values():
        coordinator = FressnapfTrackerDataUpdateCoordinator(
            hass,
            entry,
            Device(
                serialnumber=subentry.data[CONF_SERIAL_NUMBER],
                token=subentry.data[CONF_DEVICE_TOKEN],
            ),
        )
        await coordinator.async_config_entry_first_refresh()

        entry.runtime_data[subentry.subentry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
