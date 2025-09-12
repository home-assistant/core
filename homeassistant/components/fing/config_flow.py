"""Config flow file."""

from contextlib import suppress
import logging
from typing import Any

from fing_agent_api import FingAgent
import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_IP_ADDRESS, CONF_PORT

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
            devices_response = None
            agent_info_response = None

            self._async_abort_entries_match(
                {CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]}
            )

            fing_api = FingAgent(user_input)

            try:
                devices_response = await fing_api.get_devices()

                with suppress(httpx.ConnectError):
                    # The suppression is needed because the get_agent_info method isn't available for desktop agents
                    agent_info_response = await fing_api.get_agent_info()

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
                httpx.CookieConflict,
                httpx.StreamError,
                Exception,
            ) as ex:
                _LOGGER.error("Unexpected exception: %s", ex)
                errors["base"] = "unknown"
            else:
                if (
                    devices_response.network_id is not None
                    and len(devices_response.network_id) > 0
                ):
                    agent_name = user_input.get(CONF_IP_ADDRESS)
                    if agent_info_response is not None:
                        agent_name = agent_info_response.agent_id
                        await self.async_set_unique_id(agent_info_response.agent_id)
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"Fing Agent {agent_name}",
                            data=user_input,
                        )

                return self.async_abort(reason="api_version_error")

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_IP_ADDRESS): str,
                        vol.Required(CONF_PORT, default="49090"): str,
                        vol.Required(CONF_API_KEY): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )
