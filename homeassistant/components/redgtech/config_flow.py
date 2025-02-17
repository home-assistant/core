from homeassistant import config_entries
import voluptuous as vol
import logging
from .const import DOMAIN
from redgtech_api import RedgtechAPI

_LOGGER = logging.getLogger(__name__)

class RedgtechConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow for Redgtech integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial user step for login."""
        errors = {}
        
        if user_input is not None:
            email = user_input.get("email")
            password = user_input.get("password")
            
            api = RedgtechAPI()
            try:
                access_token = await api.login(email, password)
                if access_token:
                    _LOGGER.info("Login successful")

                    return self.async_create_entry(
                        title="Redgtech",
                        data={"access_token": access_token}
                    )
                else:
                    _LOGGER.error("Login failed: No access token received")
                    errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.error("Login failed: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("email"): str,
                vol.Required("password"): str,
            }),
            errors=errors
        )