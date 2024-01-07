"""KNX telegram trigger."""
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN
from ..telegrams import TelegramDict

# Platform type should be <DOMAIN>.<SUBMODULE_NAME>
PLATFORM_TYPE = f"{DOMAIN}.{__name__.rsplit('.', maxsplit=1)[-1]}"

CONF_KNX_GROUP_VALUE_WRITE = "knx_group_value_write"
CONF_KNX_GROUP_VALUE_READ = "knx_group_value_read"
CONF_KNX_GROUP_VALUE_RESPONSE = "knx_group_value_response"

EXTRA_FIELD_DESTINATION = "destination"  # no translation support
SIGNAL_KNX_TELEGRAM_DICT = "knx_telegram_dict"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): PLATFORM_TYPE,
        # vol.Optional(EXTRA_FIELD_DESTINATION): ga_list_validator,
        vol.Required(CONF_KNX_GROUP_VALUE_WRITE, default=True): bool,
        vol.Required(CONF_KNX_GROUP_VALUE_RESPONSE, default=True): bool,
        vol.Required(CONF_KNX_GROUP_VALUE_READ, default=False): bool,
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
    dst_addresses: list[str] = config.get(EXTRA_FIELD_DESTINATION, [])
    job = HassJob(action, f"KNX device trigger {trigger_info}")

    print("trigger_data: ", trigger_data)

    @callback
    def async_call_trigger_action(telegram: TelegramDict) -> None:
        """Filter Telegram and call trigger action."""
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
