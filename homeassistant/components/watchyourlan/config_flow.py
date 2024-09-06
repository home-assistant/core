"""Config flow for WatchYourLAN integration."""

import logging
from typing import Any

from httpx import ConnectError, HTTPStatusError
import voluptuous as vol
from watchyourlanclient import WatchYourLANClient

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_SSL, CONF_URL
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Schema for the user setup form
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_SSL, default=False): bool,
    }
)


class WatchYourLANConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WatchYourLAN."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                # Use the WatchYourLANClient to validate the connection
                api_client = WatchYourLANClient(
                    base_url=user_input[CONF_URL], async_mode=True
                )
                hosts = await api_client.get_all_hosts()
                if not hosts:
                    raise CannotConnect  # noqa: TRY301
            except (CannotConnect, ConnectError, HTTPStatusError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during WatchYourLAN setup")
                errors["base"] = "unknown"
            else:
                # Return a config entry on successful connection
                return self.async_create_entry(
                    title="WatchYourLAN", data={"url": user_input[CONF_URL]}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the WatchYourLAN API."""
