from homeassistant import config_entries
import voluptuous as vol
import aiohttp
import logging
from .const import DOMAIN, API_URL

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
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f'{API_URL}/home_assistant/login',
                        json={'email': email, 'password': password}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            access_token = data.get("data", {}).get("access_token")
                            if access_token:
                                _LOGGER.info("Login successful")

                                return self.async_create_entry(
                                    title="Redgtech",
                                    data={"access_token": access_token}
                                )
                            else:
                                _LOGGER.error("Login failed: No access token received")
                                errors["base"] = "invalid_auth"
                        else:
                            _LOGGER.error("Login failed: Invalid credentials")
                            errors["base"] = "invalid_auth"
            except aiohttp.ClientError as e:
                _LOGGER.error("Login failed: Cannot connect to server: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("email"): str,
                vol.Required("password"): str,
            }),
            errors=errors
        )