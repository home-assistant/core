"""Home Assistant trigger dispatcher."""

from typing import cast

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.automation import (
    ValidationIssueReporter,
    async_call_platform_validator,
)
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.trigger import (
    TriggerActionType,
    TriggerInfo,
    TriggerProtocol,
)
from homeassistant.helpers.typing import ConfigType


async def _async_get_trigger_platform(
    hass: HomeAssistant, platform_name: str
) -> TriggerProtocol:
    """Get trigger platform from cache or import it."""
    platform = await async_import_module(
        hass, f"homeassistant.components.homeassistant.triggers.{platform_name}"
    )
    return cast(TriggerProtocol, platform)


async def async_validate_trigger_config(
    hass: HomeAssistant,
    config: ConfigType,
    *,
    issue_reporter: ValidationIssueReporter | None = None,
) -> ConfigType:
    """Validate config."""
    platform = await _async_get_trigger_platform(hass, config[CONF_PLATFORM])
    if hasattr(platform, "async_validate_trigger_config"):
        return await async_call_platform_validator(
            platform.async_validate_trigger_config, hass, config, issue_reporter
        )

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
