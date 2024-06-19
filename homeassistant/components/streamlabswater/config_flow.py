"""Config flow for StreamLabs integration."""

from __future__ import annotations

from typing import Any

from streamlabswater.streamlabswater import StreamlabsClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER


async def validate_input(hass: HomeAssistant, api_key: str) -> None:
    """Validate the user input allows us to connect."""
    client = StreamlabsClient(api_key)
    response = await hass.async_add_executor_job(client.get_locations)
    locations = response.get("locations")

    if locations is None:
        raise CannotConnect


class StreamlabsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for StreamLabs."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                await validate_input(self.hass, user_input[CONF_API_KEY])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Streamlabs", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
