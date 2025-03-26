"""The Bosch Alarm integration."""

from __future__ import annotations

from ssl import SSLError

from bosch_alarm_mode2 import Panel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_INSTALLER_CODE, CONF_USER_CODE, DOMAIN

PLATFORMS: list[Platform] = [Platform.ALARM_CONTROL_PANEL]

type BoschAlarmConfigEntry = ConfigEntry[Panel]


async def async_setup_entry(hass: HomeAssistant, entry: BoschAlarmConfigEntry) -> bool:
    """Set up Bosch Alarm from a config entry."""

    panel = Panel(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        automation_code=entry.data.get(CONF_PASSWORD),
        installer_or_user_code=entry.data.get(
            CONF_INSTALLER_CODE, entry.data.get(CONF_USER_CODE)
        ),
    )
    try:
        await panel.connect()
    except (PermissionError, ValueError) as err:
        await panel.disconnect()
        raise ConfigEntryNotReady from err
    except (TimeoutError, OSError, ConnectionRefusedError, SSLError) as err:
        await panel.disconnect()
        raise ConfigEntryNotReady("Connection failed") from err

    entry.runtime_data = panel

    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=f"Bosch {panel.model}",
        manufacturer="Bosch Security Systems",
        model=panel.model,
        sw_version=panel.firmware_version,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BoschAlarmConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.disconnect()
    return unload_ok
