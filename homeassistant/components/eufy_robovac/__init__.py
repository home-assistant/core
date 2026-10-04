"""The Eufy RoboVac integration."""

from eufy_robovac import RoboVac, RoboVacInfo

from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import CONF_LOCAL_KEY, CONF_PROTOCOL_VERSION, PLATFORMS
from .coordinator import EufyRoboVacConfigEntry, EufyRoboVacCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: EufyRoboVacConfigEntry) -> bool:
    """Set up Eufy RoboVac from a config entry."""
    client = RoboVac(
        RoboVacInfo(
            device_id=entry.data[CONF_DEVICE_ID],
            model=entry.data[CONF_MODEL],
            name=entry.data[CONF_NAME],
            local_key=entry.data[CONF_LOCAL_KEY],
            host=entry.data[CONF_HOST],
            protocol_version=entry.data[CONF_PROTOCOL_VERSION],
        )
    )
    coordinator = EufyRoboVacCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EufyRoboVacConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
