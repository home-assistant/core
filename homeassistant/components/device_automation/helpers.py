"""Helpers for device oriented automations."""
from __future__ import annotations

from typing import cast

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from . import DeviceAutomationType, async_get_device_automation_platform
from .exceptions import InvalidDeviceAutomationConfig

DYNAMIC_VALIDATOR = {
    DeviceAutomationType.ACTION: "async_validate_action_config",
    DeviceAutomationType.CONDITION: "async_validate_condition_config",
    DeviceAutomationType.TRIGGER: "async_validate_trigger_config",
}

STATIC_VALIDATOR = {
    DeviceAutomationType.ACTION: "ACTION_SCHEMA",
    DeviceAutomationType.CONDITION: "CONDITION_SCHEMA",
    DeviceAutomationType.TRIGGER: "TRIGGER_SCHEMA",
}


async def async_validate_device_automation_config(
    hass: HomeAssistant,
    config: ConfigType,
    automation_schema: vol.Schema,
    automation_type: DeviceAutomationType,
) -> ConfigType:
    """Validate config."""
    validated_config: ConfigType = automation_schema(config)
    platform = await async_get_device_automation_platform(
        hass, validated_config[CONF_DOMAIN], automation_type
    )
    if not hasattr(platform, DYNAMIC_VALIDATOR[automation_type]):
        # Pass the unvalidated config to avoid mutating the raw config twice
        return cast(
            ConfigType, getattr(platform, STATIC_VALIDATOR[automation_type])(config)
        )

    # Only call the dynamic validator if the referenced device exists and the relevant
    # config entry is loaded
    registry = dr.async_get(hass)
    if not (device := registry.async_get(validated_config[CONF_DEVICE_ID])):
        # The device referenced by the device trigger does not exist
        raise InvalidDeviceAutomationConfig(
            f"Unknown device '{validated_config[CONF_DEVICE_ID]}'"
        )

    device_config_entry = None
    for entry_id in device.config_entries:
        if (
            not (entry := hass.config_entries.async_get_entry(entry_id))
            or entry.domain != validated_config[CONF_DOMAIN]
        ):
            continue
        device_config_entry = entry
        break

    if not device_config_entry:
        # The config entry referenced by the device trigger does not exist
        raise InvalidDeviceAutomationConfig(
            f"Device '{validated_config[CONF_DEVICE_ID]}' has no config entry from "
            f"domain '{validated_config[CONF_DOMAIN]}'"
        )

    if not await hass.config_entries.async_wait_component(device_config_entry):
        # The component could not be loaded, skip the dynamic validation
        return validated_config

    # Pass the unvalidated config to avoid mutating the raw config twice
    return cast(
        ConfigType,
        await getattr(platform, DYNAMIC_VALIDATOR[automation_type])(hass, config),
    )
