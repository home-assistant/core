"""Config flow for Informix Ultrasync Hub."""
import logging
from typing import Any, Dict, Optional
from ultrasync import UltraSync
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    CONF_HOST,
    CONF_PIN,
    CONF_ID,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant import config_entries

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def validate_input(hass: HomeAssistantType, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect.

    """
    data[CONF_ID]
    data[CONF_PIN]
    data[CONF_HOST]
    usync = UltraSync()

    # validate by attempting to authenticate with our hub
    return usync.login()

    return True


class UltraSyncConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """UltraSync config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return UltraSyncOptionsFlowHandler(config_entry)

    async def async_step_import(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by configuration file."""
        if CONF_SCAN_INTERVAL in user_input:
            user_input[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL].seconds

        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    validate_input, self.hass, user_input
                )

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

            return self.async_create_entry(
                title=user_input[CONF_HOST],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_ID): str,
                vol.Required(CONF_PIN): str,
            }),
            errors=errors,
        )

    async def async_step_init(self, user_input: Optional[ConfigType] = None):
        """Manage UltraSync options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class UltraSyncOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle UltraSync client options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[ConfigType] = None):
        """Manage UltraSync options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
