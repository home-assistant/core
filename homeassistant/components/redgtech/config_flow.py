"""Config flow for the Redgtech integration."""

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
import voluptuous as vol
import logging
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from .const import DOMAIN
from typing import Any
from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError, RedgtechAPI

_LOGGER = logging.getLogger(__name__)

class RedgtechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Flow for Redgtech integration."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial user step for login."""
        
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()
            
            api = RedgtechAPI()
            try:
                await api.login(email, password)
            except RedgtechAuthError:
                errors["base"] = "invalid_auth"
            except RedgtechConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown"
            else:
                _LOGGER.debug("Login successful, token received.")
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
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