"""Offer knx telegram automation triggers."""

from typing import Final

import voluptuous as vol
from xknx.telegram.address import DeviceGroupAddress, parse_device_group_address

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SIGNAL_KNX_TELEGRAM_DICT
from .schema import ga_validator
from .telegrams import TelegramDict

TRIGGER_TELEGRAM: Final = "telegram"

PLATFORM_TYPE_TRIGGER_TELEGRAM: Final = f"{DOMAIN}.{TRIGGER_TELEGRAM}"

CONF_KNX_DESTINATION: Final = "destination"
CONF_KNX_GROUP_VALUE_WRITE: Final = "group_value_write"
CONF_KNX_GROUP_VALUE_READ: Final = "group_value_read"
CONF_KNX_GROUP_VALUE_RESPONSE: Final = "group_value_response"
CONF_KNX_INCOMING: Final = "incoming"
CONF_KNX_OUTGOING: Final = "outgoing"

TELEGRAM_TRIGGER_OPTIONS: Final = {
    vol.Optional(CONF_KNX_GROUP_VALUE_WRITE, default=True): cv.boolean,
    vol.Optional(CONF_KNX_GROUP_VALUE_RESPONSE, default=True): cv.boolean,
    vol.Optional(CONF_KNX_GROUP_VALUE_READ, default=True): cv.boolean,
    vol.Optional(CONF_KNX_INCOMING, default=True): cv.boolean,
    vol.Optional(CONF_KNX_OUTGOING, default=True): cv.boolean,
}
TELEGRAM_TRIGGER_SCHEMA: Final = {
    vol.Optional(CONF_KNX_DESTINATION): vol.All(
        cv.ensure_list,
        [ga_validator],
    ),
    **TELEGRAM_TRIGGER_OPTIONS,
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
    """Listen for telegrams based on configuration."""
    _addresses: list[str] = config.get(CONF_KNX_DESTINATION, [])
    dst_addresses: list[DeviceGroupAddress] = [
        parse_device_group_address(address) for address in _addresses
    ]
    job = HassJob(action, f"KNX trigger {trigger_info}")
    trigger_data = trigger_info["trigger_data"]

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

        if (
            dst_addresses
            and parse_device_group_address(telegram["destination"]) not in dst_addresses
        ):
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
