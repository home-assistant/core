"""The Bosch Alarm integration."""

from __future__ import annotations

from ssl import SSLError

from bosch_alarm_mode2 import Panel

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import ConfigType

from .const import CONF_INSTALLER_CODE, CONF_USER_CODE, DOMAIN
from .services import setup_services
from .types import BoschAlarmConfigEntry

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up bosch alarm services."""
    setup_services(hass)
    return True


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
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err
    except (TimeoutError, OSError, ConnectionRefusedError, SSLError) as err:
        await panel.disconnect()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    entry.runtime_data = panel

    device_registry = dr.async_get(hass)

    mac = entry.data.get(CONF_MAC)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
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
