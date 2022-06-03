"""Validate device conditions."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

import voluptuous as vol

from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import DeviceAutomationType, async_get_device_automation_platform
from .exceptions import InvalidDeviceAutomationConfig

if TYPE_CHECKING:
    from homeassistant.helpers import condition


class DeviceAutomationConditionProtocol(Protocol):
    """Define the format of device_condition modules.

    Each module must define either CONDITION_SCHEMA or async_validate_condition_config.
    """

    CONDITION_SCHEMA: vol.Schema

    async def async_validate_condition_config(
        self, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    def async_condition_from_config(
        self, hass: HomeAssistant, config: ConfigType
    ) -> condition.ConditionCheckerType:
        """Evaluate state based on configuration."""

    async def async_get_condition_capabilities(
        self, hass: HomeAssistant, config: ConfigType
    ) -> dict[str, vol.Schema]:
        """List condition capabilities."""

    async def async_get_conditions(
        self, hass: HomeAssistant, device_id: str
    ) -> list[dict[str, Any]]:
        """List conditions."""


async def async_validate_condition_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate device condition config."""
    try:
        config = cv.DEVICE_CONDITION_SCHEMA(config)
        platform = await async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], DeviceAutomationType.CONDITION
        )
        if hasattr(platform, "async_validate_condition_config"):
            return await platform.async_validate_condition_config(hass, config)
        return cast(ConfigType, platform.CONDITION_SCHEMA(config))
    except InvalidDeviceAutomationConfig as err:
        raise vol.Invalid(str(err) or "Invalid condition configuration") from err


async def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Test a device condition."""
    platform = await async_get_device_automation_platform(
        hass, config[CONF_DOMAIN], DeviceAutomationType.CONDITION
    )
    return platform.async_condition_from_config(hass, config)
