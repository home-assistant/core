"""Home Assistant trigger dispatcher."""
import importlib

from homeassistant.const import CONF_PLATFORM


def _get_trigger_platform(config):
    return importlib.import_module(f"..triggers.{config[CONF_PLATFORM]}", __name__)


async def async_validate_trigger_config(hass, config):
    """Validate config."""
    platform = _get_trigger_platform(config)
    if hasattr(platform, "async_validate_trigger_config"):
        return await getattr(platform, "async_validate_trigger_config")(hass, config)

    return platform.TRIGGER_SCHEMA(config)


async def async_attach_trigger(hass, config, action, automation_info):
    """Attach trigger of specified platform."""
    platform = _get_trigger_platform(config)
    return await platform.async_attach_trigger(hass, config, action, automation_info)
