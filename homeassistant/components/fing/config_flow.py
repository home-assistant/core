"""Config flow file."""

import logging
from typing import Any

from fing_agent_api import FingAgent
import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .const import AGENT_IP, AGENT_KEY, AGENT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _get_data_schema(
    hass: HomeAssistant, user_input: dict[str, Any] | None = None
) -> vol.Schema:
    """Get a schema with default values."""

    if user_input is None:
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default="Fing Agent"): str,
                vol.Required(AGENT_IP): str,
                vol.Required(AGENT_PORT, default="49090"): str,
                vol.Required(AGENT_KEY): str,
            }
        )

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=user_input.get(CONF_NAME)): str,
            vol.Required(AGENT_IP, default=user_input.get(AGENT_IP)): str,
            vol.Required(AGENT_PORT, default=user_input.get(AGENT_PORT)): str,
            vol.Required(AGENT_KEY, default=user_input.get(AGENT_KEY)): str,
        }
    )


class FingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fing config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    def exception_to_message(
        self,
        exception: BaseException | None,
        errors: dict[str, str],
        description_placeholders: dict[str, str],
    ):
        """Generate error message from the exception."""
        if exception is None:
            _LOGGER.error("Unexpected error during ConfigFlow")
            errors["base"] = "unexpected_error"
            return

        _LOGGER.error("Exception raised during ConfigFlow", exc_info=exception)
        if isinstance(exception, httpx.NetworkError):
            errors["base"] = "cannot_connect"
            return

        if isinstance(exception, httpx.TimeoutException):
            errors["base"] = "timeout_connect"
            return

        if isinstance(exception, httpx.HTTPStatusError):
            description_placeholders["message"] = (
                f"{exception.response.status_code} - {exception.response.reason_phrase}"
            )
            if exception.response.status_code == 401:
                errors["base"] = "invalid_api_key"
                return
            errors["base"] = "http_status_error"
            return

        if isinstance(exception, httpx.InvalidURL):
            errors["base"] = "url_error"
            return

        errors["base"] = "unexpected_error"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up user step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None and await self._verify_data(
            user_input, errors, description_placeholders
        ):
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_get_data_schema(self.hass, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _verify_data(
        self,
        user_input: dict[str, Any],
        errors: dict[str, str],
        description_placeholders: dict[str, str],
    ) -> bool:
        """Verify the user data."""

        try:
            fing_api = FingAgent(
                user_input[AGENT_IP], user_input[AGENT_PORT], user_input[AGENT_KEY]
            )
            response = await fing_api.get_devices()
            if response.network_id is not None:
                return True

            errors["base"] = "api_version_error"
        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            httpx.CookieConflict,
            httpx.StreamError,
            Exception,
        ) as exception:
            self.exception_to_message(exception, errors, description_placeholders)

        return False
