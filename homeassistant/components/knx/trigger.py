"""Offer knx telegram automation triggers."""

from typing import Final

import voluptuous as vol
from xknx.dpt import DPTBase
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import DeviceGroupAddress, parse_device_group_address
from xknx.telegram.apci import GroupValueRead, GroupValueResponse, GroupValueWrite

from homeassistant.const import CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import DOMAIN
from .schema import ga_validator
from .telegrams import SIGNAL_KNX_TELEGRAM, TelegramDict, decode_telegram_payload
from .validation import dpt_base_type_validator

TRIGGER_TELEGRAM: Final = "telegram"

PLATFORM_TYPE_TRIGGER_TELEGRAM: Final = f"{DOMAIN}.{TRIGGER_TELEGRAM}"

CONF_KNX_DESTINATION: Final = "destination"
CONF_KNX_GROUP_VALUE_WRITE: Final = "group_value_write"
CONF_KNX_GROUP_VALUE_READ: Final = "group_value_read"
CONF_KNX_GROUP_VALUE_RESPONSE: Final = "group_value_response"
CONF_KNX_INCOMING: Final = "incoming"
CONF_KNX_OUTGOING: Final = "outgoing"


TELEGRAM_TRIGGER_SCHEMA: VolDictType = {
    vol.Optional(CONF_KNX_DESTINATION): vol.All(cv.ensure_list, [ga_validator]),
    vol.Optional(CONF_KNX_GROUP_VALUE_WRITE, default=True): cv.boolean,
    vol.Optional(CONF_KNX_GROUP_VALUE_RESPONSE, default=True): cv.boolean,
    vol.Optional(CONF_KNX_GROUP_VALUE_READ, default=True): cv.boolean,
    vol.Optional(CONF_KNX_INCOMING, default=True): cv.boolean,
    vol.Optional(CONF_KNX_OUTGOING, default=True): cv.boolean,
}
# TRIGGER_SCHEMA is exclusive to triggers, the above are used in device triggers too
TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): PLATFORM_TYPE_TRIGGER_TELEGRAM,
        vol.Optional(CONF_TYPE, default=None): vol.Any(dpt_base_type_validator, None),
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
    _transcoder = config.get(CONF_TYPE)
    trigger_transcoder = DPTBase.parse_transcoder(_transcoder) if _transcoder else None

    job = HassJob(action, f"KNX trigger {trigger_info}")
    trigger_data = trigger_info["trigger_data"]

    @callback
    def async_call_trigger_action(
        telegram: Telegram, telegram_dict: TelegramDict
    ) -> None:
        """Filter Telegram and call trigger action."""
        payload_apci = type(telegram.payload)
        if payload_apci is GroupValueWrite:
            if config[CONF_KNX_GROUP_VALUE_WRITE] is False:
                return
        elif payload_apci is GroupValueResponse:
            if config[CONF_KNX_GROUP_VALUE_RESPONSE] is False:
                return
        elif payload_apci is GroupValueRead:
            if config[CONF_KNX_GROUP_VALUE_READ] is False:
                return

        if telegram.direction is TelegramDirection.INCOMING:
            if config[CONF_KNX_INCOMING] is False:
                return
        elif config[CONF_KNX_OUTGOING] is False:
            return

        if dst_addresses and telegram.destination_address not in dst_addresses:
            return

        if (
            trigger_transcoder is not None
            and payload_apci in (GroupValueWrite, GroupValueResponse)
            and trigger_transcoder.value_type != telegram_dict["dpt_name"]
        ):
            decoded_payload = decode_telegram_payload(
                payload=telegram.payload.value,  # type: ignore[union-attr]  # checked via payload_apci
                transcoder=trigger_transcoder,
            )
            # overwrite decoded payload values in telegram_dict
            telegram_trigger_data = {**trigger_data, **telegram_dict, **decoded_payload}
        else:
            telegram_trigger_data = {**trigger_data, **telegram_dict}

        hass.async_run_hass_job(job, {"trigger": telegram_trigger_data})

    return async_dispatcher_connect(
        hass,
        signal=SIGNAL_KNX_TELEGRAM,
        target=async_call_trigger_action,
    )
