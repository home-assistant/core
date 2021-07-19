"""Offer device oriented automation."""
import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    async_get_device_automation_platform,
)
from homeassistant.const import CONF_DOMAIN

# mypy: allow-untyped-defs, no-check-untyped-defs

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    platform = await async_get_device_automation_platform(
        hass, config[CONF_DOMAIN], "trigger"
    )
    if hasattr(platform, "async_validate_trigger_config"):
        return await getattr(platform, "async_validate_trigger_config")(hass, config)

    return platform.TRIGGER_SCHEMA(config)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for trigger."""
    platform = await async_get_device_automation_platform(
        hass, config[CONF_DOMAIN], "trigger"
    )
    return await platform.async_attach_trigger(hass, config, action, automation_info)
