"""Provides device automations for Philips Hue events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import CALLBACK_TYPE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .v1.device_trigger import (
    async_attach_trigger as async_attach_trigger_v1,
    async_get_triggers as async_get_triggers_v1,
    async_validate_trigger_config as async_validate_trigger_config_v1,
)
from .v2.device_trigger import (
    async_attach_trigger as async_attach_trigger_v2,
    async_get_triggers as async_get_triggers_v2,
    async_validate_trigger_config as async_validate_trigger_config_v2,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo

    from .bridge import HueBridge


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    if DOMAIN not in hass.data:
        # happens at startup
        return config
    device_id = config[CONF_DEVICE_ID]
    # lookup device in HASS DeviceRegistry
    dev_reg: dr.DeviceRegistry = dr.async_get(hass)
    if (device_entry := dev_reg.async_get(device_id)) is None:
        raise InvalidDeviceAutomationConfig(f"Device ID {device_id} is not valid")

    for conf_entry_id in device_entry.config_entries:
        if conf_entry_id not in hass.data[DOMAIN]:
            continue
        bridge: HueBridge = hass.data[DOMAIN][conf_entry_id]
        if bridge.api_version == 1:
            return await async_validate_trigger_config_v1(bridge, device_entry, config)
        return await async_validate_trigger_config_v2(bridge, device_entry, config)
    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    device_id = config[CONF_DEVICE_ID]
    # lookup device in HASS DeviceRegistry
    dev_reg: dr.DeviceRegistry = dr.async_get(hass)
    if (device_entry := dev_reg.async_get(device_id)) is None:
        raise InvalidDeviceAutomationConfig(f"Device ID {device_id} is not valid")

    for conf_entry_id in device_entry.config_entries:
        if conf_entry_id not in hass.data[DOMAIN]:
            continue
        bridge: HueBridge = hass.data[DOMAIN][conf_entry_id]
        if bridge.api_version == 1:
            return await async_attach_trigger_v1(
                bridge, device_entry, config, action, trigger_info
            )
        return await async_attach_trigger_v2(
            bridge, device_entry, config, action, trigger_info
        )
    raise InvalidDeviceAutomationConfig(
        f"Device ID {device_id} is not found on any Hue bridge"
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Get device triggers for given (hass) device id."""
    if DOMAIN not in hass.data:
        return []
    # lookup device in HASS DeviceRegistry
    dev_reg: dr.DeviceRegistry = dr.async_get(hass)
    if (device_entry := dev_reg.async_get(device_id)) is None:
        raise ValueError(f"Device ID {device_id} is not valid")

    # Iterate all config entries for this device
    # and work out the bridge version
    for conf_entry_id in device_entry.config_entries:
        if conf_entry_id not in hass.data[DOMAIN]:
            continue
        bridge: HueBridge = hass.data[DOMAIN][conf_entry_id]

        if bridge.api_version == 1:
            return async_get_triggers_v1(bridge, device_entry)
        return async_get_triggers_v2(bridge, device_entry)
    return []
