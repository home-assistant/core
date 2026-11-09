"""The met_eireann component."""

from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant

from .coordinator import MetEireannConfigEntry, MetEireannUpdateCoordinator

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MetEireannConfigEntry
) -> None:
    """Set up Met Éireann as config entry."""
    coordinator = MetEireannUpdateCoordinator(hass, config_entry=config_entry)
    await coordinator.async_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MetEireannConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: MetEireannConfigEntry
) -> None:
    """Migrate old config entry."""

    if entry.version < 2:
        data = dict(entry.data)
        long = data.pop(CONF_LONGITUDE)
        lat = data.pop(CONF_LATITUDE)
        data[CONF_LOCATION] = {CONF_LATITUDE: lat, CONF_LONGITUDE: long}
        hass.config_entries.async_update_entry(entry, data=data, version=2)
