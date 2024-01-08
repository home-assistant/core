"""Provides device triggers for KNX."""

from __future__ import annotations

from typing import Any, Final

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import KNXModule, trigger
from .const import DOMAIN
from .project import KNXProject
from .trigger import (
    CONF_KNX_DESTINATION,
    CONF_KNX_GROUP_VALUE_READ,
    CONF_KNX_GROUP_VALUE_RESPONSE,
    CONF_KNX_GROUP_VALUE_WRITE,
    CONF_KNX_INCOMING,
    CONF_KNX_OUTGOING,
    PLATFORM_TYPE_TRIGGER_TELEGRAM,
    TELEGRAM_TRIGGER_SCHEMA,
    TRIGGER_SCHEMA as TRIGGER_TRIGGER_SCHEMA,
)

TRIGGER_TELEGRAM: Final = "telegram"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): TRIGGER_TELEGRAM,
        **TELEGRAM_TRIGGER_SCHEMA,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for KNX devices."""
    triggers = []

    knx: KNXModule = hass.data[DOMAIN]
    if knx.interface_device.device.id == device_id:
        # Add trigger for KNX telegrams to interface device
        triggers.append(
            {
                # Default fields when initializing the trigger
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: TRIGGER_TELEGRAM,
                # Set default values for trigger options here
                CONF_KNX_GROUP_VALUE_WRITE: True,
                CONF_KNX_GROUP_VALUE_RESPONSE: True,
                CONF_KNX_GROUP_VALUE_READ: True,
                CONF_KNX_INCOMING: True,
                CONF_KNX_OUTGOING: True,
            }
        )

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    project: KNXProject = hass.data[DOMAIN].project
    options = [
        selector.SelectOptionDict(value=ga.address, label=f"{ga.address} - {ga.name}")
        for ga in project.group_addresses.values()
    ]
    is_legacy_config = not all(
        key in config
        for key in (
            CONF_KNX_GROUP_VALUE_WRITE,
            CONF_KNX_GROUP_VALUE_RESPONSE,
            CONF_KNX_GROUP_VALUE_READ,
            CONF_KNX_INCOMING,
            CONF_KNX_OUTGOING,
        )
    )
    default_selectors = {
        vol.Optional(CONF_KNX_DESTINATION): selector.SelectSelector(
            selector.SelectSelectorConfig(
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=True,
                custom_value=True,
                options=options,
            ),
        ),
    }
    additional_selectors = {
        # need to be set in async_get_triggers to have proper default values
        vol.Required(CONF_KNX_GROUP_VALUE_WRITE): selector.BooleanSelector(),
        vol.Required(CONF_KNX_GROUP_VALUE_RESPONSE): selector.BooleanSelector(),
        vol.Required(CONF_KNX_GROUP_VALUE_READ): selector.BooleanSelector(),
        vol.Required(CONF_KNX_INCOMING): selector.BooleanSelector(),
        vol.Required(CONF_KNX_OUTGOING): selector.BooleanSelector(),
    }
    return {
        "extra_fields": vol.Schema(
            {
                **default_selectors,
                **(additional_selectors if not is_legacy_config else {}),
            }
        )
    }


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    # Remove device trigger specific fields and add trigger platform identifier
    trigger_config = {
        key: config[key] for key in (config.keys() & TELEGRAM_TRIGGER_SCHEMA.keys())
    } | {CONF_PLATFORM: PLATFORM_TYPE_TRIGGER_TELEGRAM}

    try:
        TRIGGER_TRIGGER_SCHEMA(trigger_config)
    except vol.Invalid as err:
        raise InvalidDeviceAutomationConfig(f"{err}") from err

    return await trigger.async_attach_trigger(
        hass, config=trigger_config, action=action, trigger_info=trigger_info
    )
