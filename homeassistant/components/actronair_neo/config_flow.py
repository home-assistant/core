"""Setup config flow for Actron Neo integration."""

from typing import Any

from actron_neo_api import ActronNeoAPI, ActronNeoAPIError, ActronNeoAuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import instance_id

from .const import _LOGGER, DOMAIN

ACTRON_AIR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ActronNeoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Actron Air Neo."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            _LOGGER.debug("Connecting to Actron Neo API")
            try:
                api = ActronNeoAPI(username, password)
                instance_uuid = await instance_id.async_get(self.hass)
                await api.request_pairing_token("HomeAssistant", instance_uuid)
                await api.refresh_token()
                user_data = await api.get_user()
            except ActronNeoAuthError:
                errors["base"] = "invalid_auth"
            except ActronNeoAPIError:
                errors["base"] = "api_error"
            else:
                await self.async_set_unique_id(user_data["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_API_TOKEN: api.pairing_token,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=ACTRON_AIR_SCHEMA,
            errors=errors,
        )
