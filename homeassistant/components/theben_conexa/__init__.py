"""The Theben Conexa Smartmeter gateway integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SmgwSensorCoordinator, ThebenConfigEntry

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ThebenConfigEntry) -> None:
    """Set up Theben Conexa Smartmeter gateway from a config entry."""

    coordinator = SmgwSensorCoordinator(hass, entry)
    await coordinator.async_init()
    entry.runtime_data = coordinator

    # first_refresh means get initial data
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ThebenConfigEntry) -> None:
    """Unload a config entry.

    The Conexa http based query protocol does not need any cleanup
    """
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
