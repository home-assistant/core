"""Offer device oriented automation."""

from __future__ import annotations

from typing import Any, Protocol

import voluptuous as vol

from homeassistant.const import CONF_DOMAIN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import (
    TriggerActionType,
    TriggerInfo,
    TriggerProtocol,
)
from homeassistant.helpers.typing import ConfigType

from . import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    DeviceAutomationType,
    async_get_device_automation_platform,
)
from .helpers import async_validate_device_automation_config

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA)


class DeviceAutomationTriggerProtocol(TriggerProtocol, Protocol):
    """Define the format of device_trigger modules.

    Each module must define either TRIGGER_SCHEMA or async_validate_trigger_config
    from TriggerProtocol.
    """

    async def async_get_trigger_capabilities(
        self, hass: HomeAssistant, config: ConfigType
    ) -> dict[str, vol.Schema]:
        """List trigger capabilities."""

    async def async_get_triggers(
        self, hass: HomeAssistant, device_id: str
    ) -> list[dict[str, Any]]:
        """List triggers."""


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    return await async_validate_device_automation_config(
        hass, config, TRIGGER_SCHEMA, DeviceAutomationType.TRIGGER
    )


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for trigger."""
    platform = await async_get_device_automation_platform(
        hass, config[CONF_DOMAIN], DeviceAutomationType.TRIGGER
    )
    return await platform.async_attach_trigger(hass, config, action, trigger_info)
