"""Config flow for WatchYourLAN integration."""

import logging
from typing import Any

from httpx import ConnectError, HTTPStatusError
import voluptuous as vol
from watchyourlanclient import WatchYourLANClient

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Schema for the user setup form
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
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
                    base_url=user_input[CONF_URL],
                    async_mode=True,
                    verify_ssl=user_input[CONF_VERIFY_SSL],
                )
                hosts = await api_client.get_all_hosts()
            except (ConnectError, HTTPStatusError) as exc:
                _LOGGER.error("Connection error during setup: %s", exc)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            if not hosts:
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(
                    title="WatchYourLAN", data={"url": user_input[CONF_URL]}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
