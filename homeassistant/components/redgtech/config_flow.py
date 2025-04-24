"""Config flow for the Redgtech integration."""

from homeassistant.config_entries import ConfigFlow
import voluptuous as vol
import logging
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_ACCESS_TOKEN
from .const import DOMAIN
from typing import Any
from homeassistant.data_entry_flow import FlowResult
from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError, RedgtechAPI

_LOGGER = logging.getLogger(__name__)

class RedgtechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Flow for Redgtech integration."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial user step for login."""
        
        errors: dict[str, str] = {}

        if user_input:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            api = RedgtechAPI()
            try:
                access_token = await api.login(email, password)
            except RedgtechAuthError:
                _LOGGER.error("Invalid authentication credentials")
                errors["base"] = "invalid_auth"
            except RedgtechConnectionError:
                _LOGGER.error("Unable to connect to the Redgtech API")
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error("Unexpected error during login: %s", e)
                errors["base"] = "unknown"
            else:
                if not access_token:
                    _LOGGER.error("Login failed: No access token received")
                    errors["base"] = "invalid_auth"
                else:
                    _LOGGER.debug("Login successful, token received.")
                    self._async_abort_entries_match({CONF_EMAIL: email})
                    return self.async_create_entry(
                        title=email,
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            CONF_ACCESS_TOKEN: access_token
                        }
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )
