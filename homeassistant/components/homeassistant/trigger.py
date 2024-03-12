"""Home Assistant trigger dispatcher."""

import importlib

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import (
    TriggerActionType,
    TriggerInfo,
    TriggerProtocol,
)
from homeassistant.helpers.typing import ConfigType

DATA_TRIGGER_PLATFORMS = "homeassistant_trigger_platforms"


def _get_trigger_platform(platform_name: str) -> TriggerProtocol:
    """Get trigger platform."""
    return importlib.import_module(f"..triggers.{platform_name}", __name__)


async def _async_get_trigger_platform(
    hass: HomeAssistant, platform_name: str
) -> TriggerProtocol:
    """Get trigger platform from cache or import it."""
    cache: dict[str, TriggerProtocol] = hass.data.setdefault(DATA_TRIGGER_PLATFORMS, {})
    if platform := cache.get(platform_name):
        return platform
    platform = await hass.async_add_import_executor_job(
        _get_trigger_platform, platform_name
    )
    cache[platform_name] = platform
    return platform


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    platform = await _async_get_trigger_platform(hass, config[CONF_PLATFORM])
    if hasattr(platform, "async_validate_trigger_config"):
        return await platform.async_validate_trigger_config(hass, config)

    return platform.TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach trigger of specified platform."""
    platform = await _async_get_trigger_platform(hass, config[CONF_PLATFORM])
    return await platform.async_attach_trigger(hass, config, action, trigger_info)
