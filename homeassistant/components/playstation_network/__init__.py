"""The PlayStation Network integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import ASSETS_PATH, CONF_NPSSO
from .coordinator import PlaystationNetworkConfigEntry, PlaystationNetworkCoordinator
from .helpers import PlaystationNetwork

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Set up Playstation Network from a config entry."""

    psn = PlaystationNetwork(hass, entry.data[CONF_NPSSO])

    coordinator = PlaystationNetworkCoordinator(hass, psn, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    files_path = Path(__file__).parent / "static"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(ASSETS_PATH, str(files_path), cache_headers=True),
        ]
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
