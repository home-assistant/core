"""The Bosch Alarm integration."""

from __future__ import annotations

import asyncio
import ssl

import bosch_alarm_mode2

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_INSTALLER_CODE, CONF_USER_CODE
from .coordinator import BoschAlarmCoordinator

type BoschAlarmConfigEntry = ConfigEntry[BoschAlarmCoordinator]

PLATFORMS: list[Platform] = [Platform.ALARM_CONTROL_PANEL]


async def async_setup_entry(hass: HomeAssistant, entry: BoschAlarmConfigEntry) -> bool:
    """Set up Bosch Alarm from a config entry."""
    panel = bosch_alarm_mode2.Panel(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        automation_code=entry.data.get(CONF_PASSWORD, None),
        installer_or_user_code=entry.data.get(
            CONF_INSTALLER_CODE, entry.data.get(CONF_USER_CODE, None)
        ),
    )

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

    entry.runtime_data = BoschAlarmCoordinator(hass, entry, panel)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
