from homeassistant import config_entries
import voluptuous as vol
import logging
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_ACCESS_TOKEN
from .const import DOMAIN
from .coordinator import RedgtechDataUpdateCoordinator
from typing import Any, Dict, Optional
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class RedgtechConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow for Redgtech integration."""

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial user step for login."""
        
        errors: dict[str, str] = {}

        if user_input:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            coordinator = RedgtechDataUpdateCoordinator(self.hass, None)
            try:
                access_token = await coordinator.login(email, password)
                if not access_token:
                    raise InvalidAuth
            except InvalidAuth:
                _LOGGER.error("Login failed: Invalid authentication")
                errors["base"] = "invalid_auth"
            except CannotConnect:
                _LOGGER.error("Login failed: Cannot connect to the server")
                errors["base"] = "cannot_connect"
            else:
                _LOGGER.debug("Login successful, token received.")
                self._async_abort_entries_match({CONF_EMAIL: email})
                return self.async_create_entry(
                    title="Redgtech",
                    data={
                        CONF_EMAIL: email,
                        CONF_ACCESS_TOKEN: access_token
                    }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors
        )
