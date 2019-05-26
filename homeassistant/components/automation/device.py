"""Offer device oriented automation."""
import importlib
import voluptuous as vol

from homeassistant.const import CONF_DOMAIN, CONF_PLATFORM
from homeassistant.loader import async_get_integration


def _domain_validator(config):
    """Validate it is a valid  domain or platform."""
    try:
        platform = importlib.import_module(
            '...{}.device_automation'.format(config[CONF_DOMAIN]), __name__)
    except ImportError:
        raise vol.Invalid('Invalid device specified') from None

    return platform.TRIGGER_SCHEMA(config)


TRIGGER_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_PLATFORM): 'device',
    vol.Required(CONF_DOMAIN): str,
}, extra=vol.ALLOW_EXTRA), _domain_validator)


async def async_trigger(hass, config, action, automation_info):
    """Listen for trigger."""
    integration = await async_get_integration(hass, config[CONF_DOMAIN])
    platform = integration.get_platform('device_automation')
    return await platform.async_trigger(hass, config, action, automation_info)
