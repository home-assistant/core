"""The System Nexa 2 integration."""

from functools import partial
import logging
from typing import Final

from sn2 import DeviceInitializationError
from sn2.device import (
    ConnectionStatus,
    Device,
    OnOffSetting,
    Setting,
    SettingsUpdate,
    StateChange,
    UpdateEvent,
)
import voluptuous as vol

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .helpers import NexaSystem2RuntimeData, SystemNexa2ConfigEntry
from .switch import ConfigurationSwitch, SN2SwitchPlug

_LOGGER = logging.getLogger(__name__)

DOMAIN = "systemnexa2"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({})},
    extra=vol.ALLOW_EXTRA,
)
PLATFORMS: Final = [Platform.SWITCH]


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the component from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SystemNexa2ConfigEntry) -> bool:
    """Set up from a config entry."""
    entry_process_update = partial(_process_update, entry)
    device = Device(host=entry.data[CONF_HOST], on_update=entry_process_update)
    try:
        await device.initialize()
    except DeviceInitializationError as e:
        raise ConfigEntryNotReady from e
    if device.info_data is None:
        return False

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="NEXA",
        name=device.info_data.name,
        model=device.info_data.model,
        sw_version=device.info_data.sw_version,
        hw_version=str(device.info_data.hw_version),
    )
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="NEXA",
        name=device.info_data.name,
        model=device.info_data.model,
        sw_version=device.info_data.sw_version,
        hw_version=str(device.info_data.hw_version),
    )
    entry.runtime_data = NexaSystem2RuntimeData(device=device, device_info=device_info)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await device.connect()

    return True


def _handle_connection_status(
    entry: SystemNexa2ConfigEntry, *, connected: bool
) -> None:
    """Handle connection status updates."""
    for entity in entry.runtime_data.config_entries:
        if entity.available != connected:
            entity.available = connected
            entity.async_write_ha_state()


def _handle_state_change(entry: SystemNexa2ConfigEntry, state: float) -> None:
    """Handle state change updates."""
    main_entry = entry.runtime_data.main_entry
    if isinstance(main_entry, SN2SwitchPlug):
        main_entry.handle_state_update(state=bool(state))


def _handle_settings_update(
    entry: SystemNexa2ConfigEntry, settings: list[Setting]
) -> None:
    """Handle settings updates."""
    for entity in entry.runtime_data.config_entries:
        if isinstance(entity, ConfigurationSwitch):
            for setting in settings:
                if isinstance(setting, OnOffSetting) and entity.name == setting.name:
                    entity.handle_state_update(is_on=setting.is_enabled())


async def _process_update(
    entry: SystemNexa2ConfigEntry, update_event: UpdateEvent
) -> None:
    match update_event:
        case ConnectionStatus(connected):
            _handle_connection_status(entry, connected=connected)
        case StateChange(state):
            _handle_state_change(entry, state)
        case SettingsUpdate(settings):
            _handle_settings_update(entry, settings)


async def async_unload_entry(
    hass: HomeAssistant, entry: SystemNexa2ConfigEntry
) -> bool:
    """Unload a config entry."""
    if entry.runtime_data.device:
        _LOGGER.info("Unload")
        await entry.runtime_data.device.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
