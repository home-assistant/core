"""The Home Assistant Yellow integration."""
from __future__ import annotations

from homeassistant.components.hassio import get_os_info
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant Yellow config entry."""
    if (os_info := get_os_info(hass)) is None:
        # The hassio integration has not yet fetched data from the supervisor
        raise ConfigEntryNotReady

    board: str | None
    if (board := os_info.get("board")) is None or not board == "yellow":
        # Not running on a Home Assistant Yellow, Home Assistant may have been migrated
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    await hass.config_entries.flow.async_init(
        "zha",
        context={"source": "hardware"},
        data={
            "name": "Yellow",
            "port": {
                "path": "/dev/ttyAMA1",
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "radio_type": "efr32",
        },
    )

    return True
