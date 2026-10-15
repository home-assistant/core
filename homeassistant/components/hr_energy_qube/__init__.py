"""The Qube Heat Pump integration."""

from python_qube_heatpump import QubeClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import QubeCoordinator

type QubeConfigEntry = ConfigEntry[QubeCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> None:
    """Set up Qube Heat Pump from a config entry."""
    client = QubeClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = QubeCoordinator(hass, client, entry)

    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.client.close()
