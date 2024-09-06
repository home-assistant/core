"""Config flow for WatchYourLAN integration."""

import logging

import voluptuous as vol
from watchyourlanclient import WatchYourLANClient

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Schema for the user setup form
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=8840): int,
        vol.Optional(CONF_SSL, default=False): bool,
    }
)


class WatchYourLANConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WatchYourLAN."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # Validate input and construct the URL
                proto = "https" if user_input[CONF_SSL] else "http"
                target = f"{proto}://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"

                # Use the WatchYourLANClient to validate the connection
                api_client = WatchYourLANClient(base_url=target, async_mode=True)
                hosts = await api_client.get_all_hosts()
                if not hosts:
                    raise CannotConnect  # noqa: TRY301

                # Return a config entry on successful connection
                return self.async_create_entry(
                    title="WatchYourLAN", data={"url": target}
                )

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during WatchYourLAN setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the WatchYourLAN API."""
