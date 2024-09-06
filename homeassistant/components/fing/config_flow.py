"""Config flow file."""

from typing import Any

from fing_agent_api import FingAgent
import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .const import AGENT_IP, AGENT_KEY, AGENT_PORT, DOMAIN


def _get_data_schema(
    hass: HomeAssistant, config_entry: ConfigEntry | None = None
) -> vol.Schema:
    """Get a schema with default values."""

    if config_entry is None:
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
            vol.Required(CONF_NAME, default=config_entry.data.get(CONF_NAME)): str,
            vol.Required(AGENT_IP, default=config_entry.data.get(AGENT_IP)): str,
            vol.Required(AGENT_PORT, default=config_entry.data.get(AGENT_PORT)): str,
            vol.Required(AGENT_KEY, default=config_entry.data.get(AGENT_KEY)): str,
        }
    )


class FingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fing config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    def exception_to_message(self, exception: BaseException | None):
        """Generate error message from the exception."""
        if exception is None:
            return "Connection verification raised an unknown exception."
        if isinstance(exception, httpx.HTTPError):
            return f"HTTP exception -> Args: {exception.args}"
        if isinstance(exception, httpx.InvalidURL):
            return f"Invalid URL exception -> Args: {exception.args}"
        if isinstance(exception, httpx.CookieConflict):
            return f"CookieConflict exception -> Args: {exception.args}"
        if isinstance(exception, httpx.StreamError):
            return f"Stream error exception -> Args: {exception.args}"
        return f"Generic exception raised -> Args: {exception.args}"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up user step."""
        errors: dict[str, str] = {}

        if user_input is not None and await self._verify_data(user_input, errors):
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_get_data_schema(self.hass),
            errors=errors,
        )

    async def _verify_data(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> bool:
        """Verify the user data."""

        try:
            fing_api = FingAgent(
                user_input[AGENT_IP], user_input[AGENT_PORT], user_input[AGENT_KEY]
            )
            response = await fing_api.get_devices()
            if response.network_id is not None:
                return True

            errors["base"] = "Network ID parameter is empty. Use the latest API."
        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            httpx.CookieConflict,
            httpx.StreamError,
            Exception,
        ) as exception:
            errors["base"] = self.exception_to_message(exception)

        return False
