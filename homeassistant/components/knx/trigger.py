"""Offer knx telegram automation triggers."""
from typing import Final

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SIGNAL_KNX_TELEGRAM_DICT
from .schema import ga_list_validator
from .telegrams import TelegramDict

TRIGGER_TELEGRAM: Final = "telegram"

PLATFORM_TYPE_TRIGGER_TELEGRAM = f"{DOMAIN}.{TRIGGER_TELEGRAM}"

CONF_KNX_DESTINATION = "destination"
CONF_KNX_GROUP_VALUE_WRITE = "group_value_write"
CONF_KNX_GROUP_VALUE_READ = "group_value_read"
CONF_KNX_GROUP_VALUE_RESPONSE = "group_value_response"
CONF_KNX_INCOMING = "incoming"
CONF_KNX_OUTGOING = "outgoing"

TELEGRAM_TRIGGER_SCHEMA = {
    vol.Optional(CONF_KNX_DESTINATION): ga_list_validator,
    vol.Optional(CONF_KNX_GROUP_VALUE_WRITE, default=True): cv.boolean,
    vol.Optional(CONF_KNX_GROUP_VALUE_RESPONSE, default=True): cv.boolean,
    vol.Optional(CONF_KNX_GROUP_VALUE_READ, default=True): cv.boolean,
    vol.Optional(CONF_KNX_INCOMING, default=True): cv.boolean,
    vol.Optional(CONF_KNX_OUTGOING, default=True): cv.boolean,
}

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): PLATFORM_TYPE_TRIGGER_TELEGRAM,
        **TELEGRAM_TRIGGER_SCHEMA,
    }
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for events based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    dst_addresses: list[str] = config.get(CONF_KNX_DESTINATION, [])
    job = HassJob(action, f"KNX device trigger {trigger_info}")

    @callback
    def async_call_trigger_action(telegram: TelegramDict) -> None:
        """Filter Telegram and call trigger action."""
        if telegram["telegramtype"] == "GroupValueWrite":
            if config[CONF_KNX_GROUP_VALUE_WRITE] is False:
                return
        elif telegram["telegramtype"] == "GroupValueResponse":
            if config[CONF_KNX_GROUP_VALUE_RESPONSE] is False:
                return
        elif telegram["telegramtype"] == "GroupValueRead":
            if config[CONF_KNX_GROUP_VALUE_READ] is False:
                return

        if telegram["direction"] == "Incoming":
            if config[CONF_KNX_INCOMING] is False:
                return
        elif config[CONF_KNX_OUTGOING] is False:
            return

        if dst_addresses and telegram["destination"] not in dst_addresses:
            return

        hass.async_run_hass_job(
            job,
            {"trigger": {**trigger_data, **telegram}},
        )

    return async_dispatcher_connect(
        hass,
        signal=SIGNAL_KNX_TELEGRAM_DICT,
        target=async_call_trigger_action,
    )
