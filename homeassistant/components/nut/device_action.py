"""Provides device actions for Network UPS Tools (NUT)."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import NutRuntimeData
from .const import DOMAIN, INTEGRATION_SUPPORTED_COMMANDS

ACTION_TYPES = {cmd.replace(".", "_") for cmd in INTEGRATION_SUPPORTED_COMMANDS}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for Network UPS Tools (NUT) devices."""
    if (
        runtime_data := _get_runtime_data_from_device_id(hass, device_id, False)
    ) is None:
        return []
    base_action = {
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }
    return [
        {CONF_TYPE: _get_device_action_name(command_name)} | base_action
        for command_name in runtime_data.user_available_commands
    ]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""

    device_action_name: str = config[CONF_TYPE]
    command_name = _get_command_name(device_action_name)
    device_id: str = config[CONF_DEVICE_ID]

    runtime_data = _get_runtime_data_from_device_id(hass, device_id, True)

    if runtime_data:
        await runtime_data.data.async_run_command(command_name)


def _get_device_action_name(command_name: str) -> str:
    return command_name.replace(".", "_")


def _get_command_name(device_action_name: str) -> str:
    return device_action_name.replace("_", ".")


def _get_runtime_data_from_device_id(
    hass: HomeAssistant, device_id: str, allow_exceptions: bool
) -> NutRuntimeData | None:
    device_registry = dr.async_get(hass)
    if (device := device_registry.async_get(device_id)) is None:
        if allow_exceptions:
            raise InvalidDeviceAutomationConfig(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={
                    "device_id": device_id,
                },
            )
        return None

    for config_entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(config_entry_id)
        if (
            entry
            and entry.domain == DOMAIN
            and entry.state is ConfigEntryState.LOADED
            and hasattr(entry, "runtime_data")
            and isinstance(entry.runtime_data, NutRuntimeData)
        ):
            return entry.runtime_data

    if allow_exceptions:
        raise InvalidDeviceAutomationConfig(
            translation_domain=DOMAIN,
            translation_key="config_invalid",
            translation_placeholders={
                "device_id": device_id,
            },
        )

    return None
