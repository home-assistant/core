"""Config flow file."""

import logging
from typing import Any

from fing_agent_api import FingAgent
import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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
                vol.Required(AGENT_IP): str,
                vol.Required(AGENT_PORT, default="49090"): str,
                vol.Required(AGENT_KEY): str,
            }
        )

    return vol.Schema(
        {
            vol.Required(AGENT_IP, default=user_input.get(AGENT_IP)): str,
            vol.Required(AGENT_PORT, default=user_input.get(AGENT_PORT)): str,
            vol.Required(AGENT_KEY, default=user_input.get(AGENT_KEY)): str,
        }
    )


class FingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fing config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up user step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            try:
                existing_entries = [
                    entry
                    for entry in self._async_current_entries()
                    if entry.data.get(AGENT_IP) == user_input[AGENT_IP]
                ]
                if existing_entries:
                    return self.async_abort(reason="already_configured")

                fing_api = FingAgent(
                    user_input[AGENT_IP], user_input[AGENT_PORT], user_input[AGENT_KEY]
                )
                response = await fing_api.get_devices()
                if response.network_id is not None:
                    return self.async_create_entry(
                        title=f"Fing Agent {user_input.get(AGENT_IP)}", data=user_input
                    )

                errors["base"] = "api_version_error"
            except httpx.NetworkError as _:
                errors["base"] = "cannot_connect"
            except httpx.TimeoutException as _:
                errors["base"] = "timeout_connect"
            except httpx.HTTPStatusError as exception:
                description_placeholders["message"] = (
                    f"{exception.response.status_code} - {exception.response.reason_phrase}"
                )
                if exception.response.status_code == 401:
                    errors["base"] = "invalid_api_key"
                else:
                    errors["base"] = "http_status_error"
            except httpx.InvalidURL as _:
                errors["base"] = "url_error"
            except (
                httpx.HTTPError,
                httpx.InvalidURL,
                httpx.CookieConflict,
                httpx.StreamError,
                Exception,
            ) as _:
                errors["base"] = "unexpected_error"

        return self.async_show_form(
            step_id="user",
            data_schema=_get_data_schema(self.hass, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )
