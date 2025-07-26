import aiohttp
import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from .const import DOMAIN, CONF_BROKER, CONF_DISCOVERY_PREFIX
from homeassistant.const import CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_DISCOVERY

_LOGGER = logging.getLogger(__name__)

class CadioMQTTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input:
            email = user_input["email"]
            _LOGGER.debug("Starting login for email: %s", email)

            session = aiohttp_client.async_get_clientsession(self.hass)
            try:
                async with session.post("https://egycad.com/cadio_api/node/api-login", json=user_input) as resp:
                    _LOGGER.debug("Login response status: %s", resp.status)

                    if resp.status != 200:
                        errors["base"] = "Internal error"
                        _LOGGER.warning("Invalid credentials for %s", email)
                    else:
                        data = await resp.json()
                        _LOGGER.debug("Received login data: %s", data)

                        mqtt_host = data.get("mqtt_host")
                        mqtt_port = data.get("mqtt_port")
                        discovery_prefix = data.get("discovery_prefix")

                        if not all([mqtt_host, mqtt_port, discovery_prefix]):
                            errors["base"] = "Login failed. Please try again"
                            _LOGGER.error("Incomplete login response: %s", data)
                        else:
                            return self.async_create_entry(
                                title=f"CADIO ({email})",
                                data={

                                    CONF_BROKER: mqtt_host,
                                    CONF_PORT: mqtt_port,
                                    CONF_USERNAME: email,
                                    CONF_PASSWORD: user_input["password"],
                                    CONF_DISCOVERY: True,
                                    CONF_DISCOVERY_PREFIX: discovery_prefix,
                                },
                            )

            except Exception as e:
                errors["base"] = "cannot_connect"
                _LOGGER.exception("Exception during login: %s", e)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("email"): str,
                vol.Required("password"): str,
            }),
            errors=errors,
        )