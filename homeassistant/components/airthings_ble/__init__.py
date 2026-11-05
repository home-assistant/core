"""The Airthings BLE integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MAX_RETRIES_AFTER_STARTUP
from .coordinator import AirthingsBLEConfigEntry, AirthingsBLEDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AirthingsBLEConfigEntry
) -> None:
    """Set up Airthings BLE device from a config entry."""
    coordinator = AirthingsBLEDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Once its setup and we know we are not going to delay
    # the startup of Home Assistant, we can set the max attempts
    # to a higher value. If the first connection attempt fails,
    # Home Assistant's built-in retry logic will take over.
    coordinator.airthings.set_max_attempts(MAX_RETRIES_AFTER_STARTUP)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: AirthingsBLEConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: AirthingsBLEConfigEntry
) -> None:
    """Migrate an Airthings BLE config entry to the current version."""
    if entry.minor_version < 2:
        # Incomplete reads created a device with an empty address. Removing it
        # also removes its entities, whose unique ids have an empty prefix.
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            if (dr.CONNECTION_BLUETOOTH, "") in device.connections:
                device_registry.async_remove_device(device.id)
        hass.config_entries.async_update_entry(entry, minor_version=2)
