"""Z-Wave JS trigger dispatcher."""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Callable, cast

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType


def _get_trigger_platform(config: ConfigType) -> ModuleType:
    """Return trigger platform."""
    return importlib.import_module(
        f"..triggers.{config[CONF_PLATFORM].split('.')[1]}", __name__
    )


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    platform = _get_trigger_platform(config)
    if hasattr(platform, "async_validate_trigger_config"):
        return cast(
            ConfigType,
            await getattr(platform, "async_validate_trigger_config")(hass, config),
        )
    assert hasattr(platform, "TRIGGER_SCHEMA")
    return cast(ConfigType, getattr(platform, "TRIGGER_SCHEMA")(config))


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: Callable,
    automation_info: dict[str, Any],
) -> Callable:
    """Attach trigger of specified platform."""
    platform = _get_trigger_platform(config)
    assert hasattr(platform, "async_attach_trigger")
    return cast(
        Callable,
        await getattr(platform, "async_attach_trigger")(
            hass, config, action, automation_info
        ),
    )
