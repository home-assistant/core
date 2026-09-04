"""The qingping_mqtt integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, Platform
from homeassistant.core import HomeAssistant

from .coordinator import QingpingMqttCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type QingpingMqttConfigEntry = ConfigEntry[QingpingMqttCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: QingpingMqttConfigEntry
) -> bool:
    """Set up qingping_mqtt from a config entry."""
    coordinator = entry.runtime_data = QingpingMqttCoordinator(
        hass, entry, entry.data[CONF_MAC]
    )
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: QingpingMqttConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
