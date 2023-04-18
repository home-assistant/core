"""Config flow for LastFm."""
from typing import Any

from pylast import LastFMNetwork, WSError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import ConfigType

from .const import CONF_USERS, DOMAIN, LOGGER, PLACEHOLDERS

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_USERS): str,
    }
)


class LastFmFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for LastFm."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize user input."""
        errors = {}
        if user_input is not None:
            lastfm_api = LastFMNetwork(api_key=user_input[CONF_API_KEY])
            final_user_input = user_input.copy()
            if isinstance(final_user_input[CONF_USERS], str):
                final_user_input[CONF_USERS] = [final_user_input[CONF_USERS]]
            try:
                for user in final_user_input[CONF_USERS]:
                    lastfm_api.get_user(user).get_playcount()
            except WSError as error:
                LOGGER.error(error)
                if error.details == "User not found":
                    errors["base"] = "invalid_account"
                elif (
                    error.details
                    == "Invalid API key - You must be granted a valid key by last.fm"
                ):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"
            except Exception:  # pylint:disable=broad-except
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(title="LastFM", data=final_user_input)
        return self.async_show_form(
            step_id="user",
            errors=errors,
            description_placeholders=PLACEHOLDERS,
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_KEY] == import_config[CONF_API_KEY]:
                return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)
