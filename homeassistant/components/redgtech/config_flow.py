from homeassistant import config_entries
import voluptuous as vol
import logging
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_ACCESS_TOKEN
from .const import DOMAIN
from redgtech_api import RedgtechAPI
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

class RedgtechConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow for Redgtech integration."""

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.FlowResult:
        """Handle the initial user step for login."""
        errors = {}
        
        if user_input is not None:
            email = user_input.get(CONF_EMAIL)
            password = user_input.get(CONF_PASSWORD)
            api = RedgtechAPI()

            try:
                access_token = await api.login(email, password)
                if access_token:
                    _LOGGER.debug("Login successful, token received.")

                    existing_entries = self._async_current_entries()
                    for entry in existing_entries:
                        if entry.data.get(CONF_ACCESS_TOKEN) == access_token:
                            return self.async_abort(reason="already_configured")

                    return self.async_create_entry(
                        title="Redgtech",
                        data={CONF_ACCESS_TOKEN: access_token}
                    )
                
                _LOGGER.error("Login failed: No access token received")
                errors["base"] = "invalid_auth"

            except Exception as e:
                _LOGGER.error("Login failed: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors
        )
