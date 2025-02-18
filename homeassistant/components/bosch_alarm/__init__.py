"""The Bosch Alarm integration."""

from __future__ import annotations

import asyncio
import ssl

import bosch_alarm_mode2

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_INSTALLER_CODE, CONF_USER_CODE
from .device import PanelConnection

PLATFORMS: list[Platform] = [Platform.ALARM_CONTROL_PANEL]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bosch Alarm from a config entry."""
    panel = bosch_alarm_mode2.Panel(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        automation_code=entry.data.get(CONF_PASSWORD, None),
        installer_or_user_code=entry.data.get(
            CONF_INSTALLER_CODE, entry.data.get(CONF_USER_CODE, None)
        ),
    )

    # The config flow sets the entries unique id to the serial number if available
    # If the panel doesn't expose it's serial number, use the entry id as a unique id instead.
    unique_id = entry.unique_id or entry.entry_id

    panel_conn = PanelConnection(panel, unique_id, entry.data[CONF_MODEL])
    entry.runtime_data = panel_conn

    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    try:
        await panel.connect()
    except (PermissionError, ValueError) as err:
        await panel.disconnect()
        raise ConfigEntryAuthFailed from err
    except (
        OSError,
        ConnectionRefusedError,
        ssl.SSLError,
        asyncio.exceptions.TimeoutError,
    ) as err:
        await panel.disconnect()
        raise ConfigEntryNotReady("Connection failed") from err

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )
    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    panel = entry.runtime_data
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await panel.disconnect()

    return unload_ok
