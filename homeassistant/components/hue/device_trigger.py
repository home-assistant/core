"""Provides device automations for Philips Hue events."""

from .v1.device_trigger import (
    async_attach_trigger as async_attach_trigger_v1,
    async_get_triggers as async_get_triggers_v1,
    async_validate_trigger_config as async_validate_trigger_config_v1,
)


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    return await async_validate_trigger_config_v1(hass, config)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    return await async_attach_trigger_v1(hass, config, action, automation_info)


async def async_get_triggers(hass, device_id):
    """List device triggers.

    Make sure device is a supported remote model.
    Retrieve the hue event object matching device entry.
    Generate device trigger list.
    """
    return await async_get_triggers_v1(hass, device_id)
