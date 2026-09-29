"""The Bitvis Power Hub integration."""

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_LISTENER_REGISTRY, DOMAIN
from .coordinator import (
    BitvisConfigEntry,
    BitvisDataUpdateCoordinator,
    async_get_listener_registry,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bitvis Power Hub integration."""
    async_get_listener_registry(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BitvisConfigEntry) -> bool:
    """Set up Bitvis Power Hub from a config entry."""
    async_get_listener_registry(hass)
    if TYPE_CHECKING:
        assert entry.unique_id is not None
    coordinator = BitvisDataUpdateCoordinator(
        hass,
        entry,
        entry.data[CONF_PORT],
        entry.unique_id,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BitvisConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_stop()
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            hass.data.pop(DATA_LISTENER_REGISTRY, None)
    return unload_ok
