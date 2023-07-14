"""Validate device conditions."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import voluptuous as vol

from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import ConditionProtocol, trace_condition_function
from homeassistant.helpers.typing import ConfigType

from . import DeviceAutomationType, async_get_device_automation_platform
from .helpers import async_validate_device_automation_config

if TYPE_CHECKING:
    from homeassistant.helpers import condition


class DeviceAutomationConditionProtocol(ConditionProtocol, Protocol):
    """Define the format of device_condition modules.

    Each module must define either CONDITION_SCHEMA or async_validate_condition_config
    from ConditionProtocol.
    """

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
    return await async_validate_device_automation_config(
        hass, config, cv.DEVICE_CONDITION_SCHEMA, DeviceAutomationType.CONDITION
    )


async def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Test a device condition."""
    platform = await async_get_device_automation_platform(
        hass, config[CONF_DOMAIN], DeviceAutomationType.CONDITION
    )
    return trace_condition_function(platform.async_condition_from_config(hass, config))
