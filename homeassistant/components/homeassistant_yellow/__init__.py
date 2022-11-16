"""The Home Assistant Yellow integration."""
from __future__ import annotations

import logging

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
    get_os_info,
)
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    get_addon_manager,
    get_zigbee_socket,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)


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

    addon_manager: AddonManager = get_addon_manager(hass)
    try:
        addon_info: AddonInfo = await addon_manager.async_get_addon_info()
    except AddonError as err:
        _LOGGER.error(err)
        raise ConfigEntryNotReady from err

    # Start the addon if it's not started
    if addon_info.state == AddonState.NOT_RUNNING:
        await addon_manager.async_start_addon()

    if addon_info.state not in (AddonState.NOT_INSTALLED, AddonState.RUNNING):
        _LOGGER.debug(
            "Multi pan addon in state %s, delaying yellow config entry setup",
            addon_info.state,
        )
        raise ConfigEntryNotReady

    if addon_info.state == AddonState.NOT_INSTALLED:
        path = "/dev/ttyAMA1"
    else:
        path = get_zigbee_socket(hass, addon_info)

    await hass.config_entries.flow.async_init(
        "zha",
        context={"source": "hardware"},
        data={
            "name": "Yellow",
            "port": {
                "path": path,
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "radio_type": "efr32",
        },
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
