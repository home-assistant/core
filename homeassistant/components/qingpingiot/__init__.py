"""The Qingping IoT integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant

from .const import DOMAIN as DOMAIN, PLATFORMS
from .coordinator import QingpingCoordinator


@dataclass
class QingpingData:
    """Runtime data for a Qingping config entry."""

    coordinator: QingpingCoordinator


type QingpingConfigEntry = ConfigEntry[QingpingData]


async def async_setup_entry(hass: HomeAssistant, entry: QingpingConfigEntry) -> bool:
    """Set up Qingping IoT from a config entry."""
    mac = entry.data[CONF_MAC]
    model = entry.data[CONF_MODEL]
    name = entry.title

    coordinator = QingpingCoordinator(hass, entry, mac, model, name)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = QingpingData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(coordinator.async_stop)
    await coordinator.async_start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: QingpingConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
