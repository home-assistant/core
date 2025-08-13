"""Validate device conditions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import voluptuous as vol

from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    Condition,
    ConditionCheckerType,
    trace_condition_function,
)
from homeassistant.helpers.typing import ConfigType

from . import DeviceAutomationType, async_get_device_automation_platform
from .helpers import async_validate_device_automation_config

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
    ) -> ConditionCheckerType:
        """Evaluate state based on configuration."""

    async def async_get_condition_capabilities(
        self, hass: HomeAssistant, config: ConfigType
    ) -> dict[str, vol.Schema]:
        """List condition capabilities."""

    async def async_get_conditions(
        self, hass: HomeAssistant, device_id: str
    ) -> list[dict[str, Any]]:
        """List conditions."""


class DeviceCondition(Condition):
    """Device condition."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize condition."""
        self._config = config
        self._hass = hass

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate device condition config."""
        return await async_validate_device_automation_config(
            hass, config, cv.DEVICE_CONDITION_SCHEMA, DeviceAutomationType.CONDITION
        )

    async def async_get_checker(self) -> condition.ConditionCheckerType:
        """Test a device condition."""
        platform = await async_get_device_automation_platform(
            self._hass, self._config[CONF_DOMAIN], DeviceAutomationType.CONDITION
        )
        return trace_condition_function(
            platform.async_condition_from_config(self._hass, self._config)
        )


CONDITIONS: dict[str, type[Condition]] = {
    "_device": DeviceCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the sun conditions."""
    return CONDITIONS
