"""Config flow for the Interlogix/Hills ComNav UltraSync Hub."""
import logging
from typing import Any, Dict, Optional

import ultrasync
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DEFAULT_NAME, DEFAULT_SCAN_INTERVAL
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class AuthFailureException(Exception):
    """A general exception we can use to track Authentication failures."""

    pass


def validate_input(hass: HomeAssistantType, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""

    usync = ultrasync.UltraSync(
        host=data[CONF_HOST], user=data[CONF_USERNAME], pin=data[CONF_PIN]
    )

    # validate by attempting to authenticate with our hub

    if not usync.login():
        # report our connection issue
        raise AuthFailureException()

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

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle user flow."""

        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input.get(CONF_HOST))
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(
                    validate_input, self.hass, user_input
                )

            except AuthFailureException:
                errors["base"] = "invalid_auth"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PIN): str,
                }
            ),
            errors=errors,
        )


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
