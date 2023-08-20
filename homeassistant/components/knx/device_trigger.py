"""Provides device triggers for KNX."""
from __future__ import annotations

from typing import Any, Final

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import KNXModule
from .const import DOMAIN
from .project import KNXProject
from .schema import ga_list_validator
from .telegrams import TelegramDict

TRIGGER_TELEGRAM: Final = "telegram"
EXTRA_FIELD_DESTINATION: Final = "destination"  # no translation support

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Optional(EXTRA_FIELD_DESTINATION): ga_list_validator,
        vol.Required(CONF_TYPE): TRIGGER_TELEGRAM,
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
                # Required fields of TRIGGER_BASE_SCHEMA
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                # Required fields of TRIGGER_SCHEMA
                CONF_TYPE: TRIGGER_TELEGRAM,
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
    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional(EXTRA_FIELD_DESTINATION): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        custom_value=True,
                        options=options,
                    ),
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
    trigger_data = trigger_info["trigger_data"]
    dst_addresses: list[str] = config.get(EXTRA_FIELD_DESTINATION, [])
    job = HassJob(action, f"KNX device trigger {trigger_info}")
    knx: KNXModule = hass.data[DOMAIN]

    @callback
    def async_call_trigger_action(telegram: TelegramDict) -> None:
        """Filter Telegram and call trigger action."""
        if dst_addresses and telegram["destination"] not in dst_addresses:
            return
        hass.async_run_hass_job(
            job,
            {"trigger": {**trigger_data, **telegram}},
        )

    return knx.telegrams.async_listen_telegram(
        async_call_trigger_action, name="KNX device trigger call"
    )
