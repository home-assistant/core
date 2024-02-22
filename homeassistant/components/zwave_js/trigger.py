"""Z-Wave JS trigger dispatcher."""
from __future__ import annotations

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import (
    TriggerActionType,
    TriggerInfo,
    TriggerProtocol,
)
from homeassistant.helpers.typing import ConfigType

from .triggers import event, value_updated

TRIGGERS = {
    "value_updated": value_updated,
    "event": event,
}


def _get_trigger_platform(config: ConfigType) -> TriggerProtocol:
    """Return trigger platform."""
    platform_split = config[CONF_PLATFORM].split(".", maxsplit=1)
    if len(platform_split) < 2 or platform_split[1] not in TRIGGERS:
        raise ValueError(f"Unknown Z-Wave JS trigger platform {config[CONF_PLATFORM]}")
    return TRIGGERS[platform_split[1]]


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    platform = _get_trigger_platform(config)
    return await platform.async_validate_trigger_config(hass, config)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach trigger of specified platform."""
    platform = _get_trigger_platform(config)
    return await platform.async_attach_trigger(hass, config, action, trigger_info)
