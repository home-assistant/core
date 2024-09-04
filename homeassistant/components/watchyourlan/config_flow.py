"""Config flow for WatchYourLAN integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN
from .options_flow import WatchYourLANOptionsFlowHandler

# Schema for the user setup form
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=8840): int,
        vol.Optional(CONF_SSL, default=False): bool,
        vol.Optional("update_interval", default=5): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
    }
)


async def validate_input(hass, data):
    """Validate the user input allows us to connect to the API."""
    proto = "https" if data[CONF_SSL] else "http"
    target = f"{proto}://{data[CONF_HOST]}:{data[CONF_PORT]}"

    async with get_async_client(hass) as client:
        response = await client.get(f"{target}/api/all")
        if response.status_code != 200:
            raise CannotConnect
    return {"title": "WatchYourLAN", "url": target}


class WatchYourLANConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WatchYourLAN."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # Validate input and construct the URL
                info = await validate_input(self.hass, user_input)
                # Store the URL in the config entry
                user_input["url"] = info["url"]
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return WatchYourLANOptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the WatchYourLAN API."""
