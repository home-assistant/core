"""Config flow for Canary."""
import logging
from requests import ConnectTimeout, HTTPError
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import Api
from .const import DEFAULT_TIMEOUT
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


def validate_input(hass: HomeAssistantType, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # constructor does login call
    canary_api = Api(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data[CONF_TIMEOUT],
    )

    return True


class CanaryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Canary."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    async def async_step_import(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by configuration file."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            if CONF_TIMEOUT not in user_input:
                user_input[CONF_TIMEOUT] = DEFAULT_TIMEOUT

            try:
                await self.hass.async_add_executor_job(
                    validate_input, self.hass, user_input
                )
            except (ConnectTimeout, HTTPError):
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

        if self.show_advanced_options:
            data_schema[
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT)
            ] = int

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors or {},
        )
