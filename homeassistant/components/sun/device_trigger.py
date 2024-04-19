"""Provides device triggers for KNX."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_OFFSET,
    CONF_PLATFORM,
    CONF_TYPE,
    SUN_EVENT_SUNRISE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import trigger
from .const import DOMAIN

TEST_TRIGGER_TYPE: Final = "test_sun_trigger"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): TEST_TRIGGER_TYPE,
        # TODO: using vol.Required fails validation if user didn't change
        #       any extra fields and they are not set in `async_get_triggers`
        #       even though they have default values
        vol.Optional("bool"): bool,
        vol.Optional("const"): bool,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for sun devices."""
    return [
        {
            # Default fields when initializing the trigger
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: TEST_TRIGGER_TYPE,
        }
    ]


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    # TODO: no translation support for extra_fields
    return {
        "extra_fields": vol.Schema(
            {
                # TODO: default values are not reflected in the UI
                vol.Required("bool", default=True): selector.BooleanSelector(),
                # TODO: ConstantSelector does not show checkbox in UI
                vol.Required("const", default=True): selector.ConstantSelector(
                    selector.ConstantSelectorConfig(label="Constant", value=True)
                ),
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
    print(f"attaching trigger\n{trigger_info=}\n{config=}")
    # Validate the configuration of the trigger
    try:
        TRIGGER_SCHEMA(config)
    except vol.Invalid as err:
        raise InvalidDeviceAutomationConfig(f"{err}") from err

    # forward dummy data to sun trigger
    trigger_config = {
        CONF_EVENT: SUN_EVENT_SUNRISE,
        CONF_OFFSET: timedelta(0),
    }
    return await trigger.async_attach_trigger(
        hass, config=trigger_config, action=action, trigger_info=trigger_info
    )
