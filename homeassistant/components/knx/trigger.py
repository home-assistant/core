"""Provide KNX automation triggers."""

from collections.abc import Callable
from typing import Any, Final, cast, override

import voluptuous as vol
from xknx.dpt import DPTBase
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import DeviceGroupAddress, parse_device_group_address
from xknx.telegram.apci import GroupValueRead, GroupValueResponse, GroupValueWrite

from homeassistant.const import CONF_OPTIONS, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from .const import SIGNAL_KNX_TELEGRAM
from .schema import ga_validator
from .telegrams import TelegramDict, decode_telegram_payload
from .validation import dpt_base_type_validator

TRIGGER_TELEGRAM: Final = "telegram"

CONF_KNX_DESTINATION: Final = "destination"
CONF_KNX_GROUP_VALUE_WRITE: Final = "group_value_write"
CONF_KNX_GROUP_VALUE_READ: Final = "group_value_read"
CONF_KNX_GROUP_VALUE_RESPONSE: Final = "group_value_response"
CONF_KNX_INCOMING: Final = "incoming"
CONF_KNX_OUTGOING: Final = "outgoing"


TELEGRAM_TRIGGER_SCHEMA: dict[vol.Marker, Any] = {
    vol.Required(CONF_KNX_DESTINATION, default=list): vol.All(
        cv.ensure_list, [ga_validator]
    ),
    vol.Optional(CONF_KNX_GROUP_VALUE_WRITE, default=True): cv.boolean,
    vol.Optional(CONF_KNX_GROUP_VALUE_RESPONSE, default=True): cv.boolean,
    vol.Optional(CONF_KNX_GROUP_VALUE_READ, default=True): cv.boolean,
    vol.Optional(CONF_KNX_INCOMING, default=True): cv.boolean,
    vol.Optional(CONF_KNX_OUTGOING, default=True): cv.boolean,
}
# the DPT type is exclusive to the telegram trigger, the above are used
# in device triggers too
_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Optional(CONF_TYPE, default=None): vol.Any(dpt_base_type_validator, None),
    **TELEGRAM_TRIGGER_SCHEMA,
}
_TELEGRAM_TRIGGER_SCHEMA = vol.Schema(
    {vol.Required(CONF_OPTIONS, default=dict): _OPTIONS_SCHEMA_DICT}
)


@callback
def async_subscribe_telegrams(
    hass: HomeAssistant,
    options: ConfigType,
    telegram_callback: Callable[[dict[str, Any]], None],
) -> CALLBACK_TYPE:
    """Call `telegram_callback` for telegrams matching the filter options.

    Shared by the telegram trigger and the interface device trigger. The payload
    passed to the callback is the telegram dict, with the values re-decoded when
    a DPT type is configured.
    """
    # an empty destination list matches every group address
    dst_addresses: list[DeviceGroupAddress] = [
        parse_device_group_address(address) for address in options[CONF_KNX_DESTINATION]
    ]
    _transcoder = options.get(CONF_TYPE)
    trigger_transcoder = DPTBase.parse_transcoder(_transcoder) if _transcoder else None

    @callback
    def async_telegram_received(
        telegram: Telegram, telegram_dict: TelegramDict
    ) -> None:
        """Filter Telegram and call the callback."""
        payload_apci = type(telegram.payload)
        if payload_apci is GroupValueWrite:
            if options[CONF_KNX_GROUP_VALUE_WRITE] is False:
                return
        elif payload_apci is GroupValueResponse:
            if options[CONF_KNX_GROUP_VALUE_RESPONSE] is False:
                return
        elif payload_apci is GroupValueRead:
            if options[CONF_KNX_GROUP_VALUE_READ] is False:
                return

        if telegram.direction is TelegramDirection.INCOMING:
            if options[CONF_KNX_INCOMING] is False:
                return
        elif options[CONF_KNX_OUTGOING] is False:
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
            telegram_callback({**telegram_dict, **decoded_payload})
            return

        telegram_callback(dict(telegram_dict))

    return async_dispatcher_connect(
        hass,
        signal=SIGNAL_KNX_TELEGRAM,
        target=async_telegram_received,
    )


class TelegramTrigger(Trigger):
    """Trigger for KNX telegrams."""

    _options: dict[str, Any]

    @override
    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config, migrating the legacy top-level fields."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _TELEGRAM_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        assert config.options is not None
        self._options = config.options

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        @callback
        def async_telegram_received(telegram_data: dict[str, Any]) -> None:
            """Run the action for a matching telegram."""
            run_action(
                telegram_data,
                f"KNX telegram to {telegram_data['destination']}",
            )

        return async_subscribe_telegrams(
            self._hass, self._options, async_telegram_received
        )


TRIGGERS: dict[str, type[Trigger]] = {
    TRIGGER_TELEGRAM: TelegramTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for KNX."""
    return TRIGGERS
