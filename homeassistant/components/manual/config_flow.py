import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv

from . import DOMAIN
from .alarm_control_panel import (
    CONF_ARMING_TIME,
    CONF_CODE,
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_TEMPLATE,
    CONF_DELAY_TIME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_TRIGGER_TIME,
    DEFAULT_ALARM_NAME,
    DEFAULT_ARMING_TIME,
    DEFAULT_DELAY_TIME,
    DEFAULT_DISARM_AFTER_TRIGGER,
    DEFAULT_TRIGGER_TIME,
    SUPPORTED_ARMING_STATES,
    SUPPORTED_PRETRIGGER_STATES,
    SUPPORTED_STATES,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(
            CONF_CODE_TEMPLATE
        ): cv.string,  # cv.template and Exclusive did not work,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(
            CONF_DISARM_AFTER_TRIGGER, default=DEFAULT_DISARM_AFTER_TRIGGER
        ): cv.boolean,
        **{
            vol.Optional(
                f"{state}_{delay_name}", default=delay_default
            ): cv.positive_int
            for state in SUPPORTED_STATES
            for (delay_name, delay_default, allowed_states) in [
                (
                    CONF_DELAY_TIME,
                    DEFAULT_DELAY_TIME.seconds,
                    SUPPORTED_PRETRIGGER_STATES,
                ),
                (
                    CONF_TRIGGER_TIME,
                    DEFAULT_TRIGGER_TIME.seconds,
                    SUPPORTED_PRETRIGGER_STATES,
                ),
                (
                    CONF_ARMING_TIME,
                    DEFAULT_ARMING_TIME.seconds,
                    SUPPORTED_ARMING_STATES,
                ),
            ]
            if state in allowed_states
        },
    }
)


class ManualConfigFlow(config_entries.ConfigFlow, domain="manual"):
    async def async_step_user(self, info):
        if info is not None:
            return self.async_create_entry(
                title=info[CONF_NAME], data={**info, "platform": DOMAIN}
            )

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)
