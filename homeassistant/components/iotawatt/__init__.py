"""The iotawatt integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .coordinator import IotawattConfigEntry, IotawattUpdater

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IotawattConfigEntry) -> bool:
    """Set up iotawatt from a config entry."""
    coordinator = IotawattUpdater(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    if entry.unique_id is None:
        if sensor := next(iter(coordinator.data["sensors"].values()), None):
            unique_id = sensor.hub_mac_address
            if any(
                other.unique_id == unique_id and other.entry_id != entry.entry_id
                for other in hass.config_entries.async_entries(entry.domain)
            ):
                raise ConfigEntryError("Duplicate IoTaWatt configuration")

            hass.config_entries.async_update_entry(entry, unique_id=unique_id)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IotawattConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
