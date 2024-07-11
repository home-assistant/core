"""The Home Assistant Yellow integration."""

from __future__ import annotations

from homeassistant.components.hassio import get_os_info, is_hassio
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    check_multi_pan_addon,
    get_zigbee_socket,
    multi_pan_addon_using_device,
)
from homeassistant.config_entries import SOURCE_HARDWARE, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import discovery_flow

from .const import RADIO_DEVICE, ZHA_HW_DISCOVERY_DATA


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant Yellow config entry."""
    if not is_hassio(hass):
        # Not running under supervisor, Home Assistant may have been migrated
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    if (os_info := get_os_info(hass)) is None:
        # The hassio integration has not yet fetched data from the supervisor
        raise ConfigEntryNotReady

    board: str | None
    if (board := os_info.get("board")) is None or board != "yellow":
        # Not running on a Home Assistant Yellow, Home Assistant may have been migrated
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    try:
        await check_multi_pan_addon(hass)
    except HomeAssistantError as err:
        raise ConfigEntryNotReady from err

    if not await multi_pan_addon_using_device(hass, RADIO_DEVICE):
        hw_discovery_data = ZHA_HW_DISCOVERY_DATA
    else:
        hw_discovery_data = {
            "name": "Yellow Multiprotocol",
            "port": {
                "path": get_zigbee_socket(),
            },
            "radio_type": "ezsp",
        }

    discovery_flow.async_create_flow(
        hass,
        "zha",
        context={"source": SOURCE_HARDWARE},
        data=hw_discovery_data,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
