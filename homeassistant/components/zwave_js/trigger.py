"""Z-Wave JS trigger dispatcher."""
from __future__ import annotations

from types import ModuleType
from typing import cast

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .triggers import event, value_updated

TRIGGERS = {
    "value_updated": value_updated,
    "event": event,
}


def _get_trigger_platform(config: ConfigType) -> ModuleType:
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
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach trigger of specified platform."""
    platform = _get_trigger_platform(config)
    assert hasattr(platform, "async_attach_trigger")
    return cast(
        CALLBACK_TYPE,
        await getattr(platform, "async_attach_trigger")(
            hass, config, action, automation_info
        ),
    )
