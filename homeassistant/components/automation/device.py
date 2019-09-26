"""Offer device oriented automation."""
import voluptuous as vol

import homeassistant.components.device_automation as device_automation
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_DOMAIN


# mypy: allow-untyped-defs, no-check-untyped-defs

TRIGGER_SCHEMA = device_automation.TRIGGER_BASE_SCHEMA.extend(extra=vol.ALLOW_EXTRA)


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    platform = await device_automation.async_get_device_automation_platform(
        hass, config, "trigger"
    )
    if not hasattr(platform, "async_get_triggers"):
        raise InvalidDeviceAutomationConfig(
            f"Integration '{config[CONF_DOMAIN]}' does not support device automation triggers"
        )

    return platform.TRIGGER_SCHEMA(config)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for trigger."""
    platform = await device_automation.async_get_device_automation_platform(
        hass, config, "trigger"
    )
    return await platform.async_attach_trigger(hass, config, action, automation_info)
