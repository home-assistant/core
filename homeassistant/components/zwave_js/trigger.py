"""Z-Wave JS trigger dispatcher."""
from __future__ import annotations

import importlib

from homeassistant.const import CONF_PLATFORM

# mypy: allow-incomplete-defs, allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs


def _get_trigger_platform(config):
    """Return trigger platform."""
    return importlib.import_module(
        f"..triggers.{config[CONF_PLATFORM].split('.')[1]}", __name__
    )


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
