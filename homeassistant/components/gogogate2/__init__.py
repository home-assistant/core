"""The gogogate2 component."""

from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant

from .common import create_data_update_coordinator
from .const import DEVICE_TYPE_GOGOGATE2
from .coordinator import GogoGateConfigEntry

PLATFORMS = [Platform.COVER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GogoGateConfigEntry) -> None:
    """Do setup of Gogogate2."""

    # Update the config entry.
    config_updates = {}
    if CONF_DEVICE not in entry.data:
        config_updates = {
            **entry.data,
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
        }

    if config_updates:
        hass.config_entries.async_update_entry(entry, data=config_updates)

    data_update_coordinator = create_data_update_coordinator(hass, entry)
    await data_update_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = data_update_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: GogoGateConfigEntry) -> None:
    """Unload Gogogate2 config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
