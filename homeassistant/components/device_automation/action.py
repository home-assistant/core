"""Device action validator."""
from __future__ import annotations

from typing import Any, Protocol, cast

import voluptuous as vol

from homeassistant.const import CONF_DOMAIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import DeviceAutomationType, async_get_device_automation_platform
from .exceptions import InvalidDeviceAutomationConfig


class DeviceAutomationActionProtocol(Protocol):
    """Define the format of device_action modules.

    Each module must define either ACTION_SCHEMA or async_validate_action_config.
    """

    ACTION_SCHEMA: vol.Schema

    async def async_validate_action_config(
        self, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    async def async_call_action_from_config(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        variables: dict[str, Any],
        context: Context | None,
    ) -> None:
        """Execute a device action."""

    async def async_get_action_capabilities(
        self, hass: HomeAssistant, config: ConfigType
    ) -> dict[str, vol.Schema]:
        """List action capabilities."""

    async def async_get_actions(
        self, hass: HomeAssistant, device_id: str
    ) -> list[dict[str, Any]]:
        """List actions."""


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    try:
        platform = await async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], DeviceAutomationType.ACTION
        )
        if hasattr(platform, "async_validate_action_config"):
            return await platform.async_validate_action_config(hass, config)
        return cast(ConfigType, platform.ACTION_SCHEMA(config))
    except InvalidDeviceAutomationConfig as err:
        raise vol.Invalid(str(err) or "Invalid action configuration") from err


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: dict[str, Any],
    context: Context | None,
) -> None:
    """Execute a device action."""
    platform = await async_get_device_automation_platform(
        hass,
        config[CONF_DOMAIN],
        DeviceAutomationType.ACTION,
    )
    await platform.async_call_action_from_config(hass, config, variables, context)
