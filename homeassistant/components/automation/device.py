"""Offer device oriented automation."""
import voluptuous as vol

import homeassistant.components.device_automation as device_automation
from homeassistant.const import CONF_DOMAIN, CONF_PLATFORM


# mypy: allow-untyped-defs, no-check-untyped-defs

TRIGGER_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLATFORM): "device", vol.Required(CONF_DOMAIN): str},
    extra=vol.ALLOW_EXTRA,
)


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    return await device_automation.async_validate_trigger_config(hass, config)


async def async_trigger(hass, config, action, automation_info):
    """Listen for trigger."""
    return await device_automation.async_trigger(hass, config, action, automation_info)
