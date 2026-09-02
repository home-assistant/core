"""Config flow for the Netis Router integration.

Provides the UI-based setup wizard that users interact with when adding the
integration via Settings > Devices & Services > Add Integration.

Flow steps:
  1. **user**: User enters host (IP), username (default "root"), and
     password (WiFi password). The flow attempts a live login + system info
     fetch to validate credentials before saving.
  2. **init** (Options Flow): User can adjust the polling interval
     (10–300 seconds) after initial setup.

Error handling maps API exceptions to user-friendly messages:
  - ``NetisAuthError``      → "invalid_auth" (wrong password/username)
  - ``NetisConnectionError`` → "cannot_connect" (unreachable host)
  - other ``NetisError``    → "unknown"
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NetisAuthError, NetisClient, NetisConnectionError, NetisError
from .const import DEFAULT_HOST, DOMAIN

# Schema for the initial setup form shown to the user.
# Password allows empty string: Netis routers in factory-default state have
# no password, and the login API accepts an empty password.
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PASSWORD, default=""): str,
    }
)


async def _test_connection(hass, host: str, password: str) -> str | None:
    """Try to log in and fetch system info.

    Returns ``None`` on success (credentials valid, router reachable), or an
    error string key on failure. The error string maps to a user-facing
    message defined in ``strings.json``.
    """
    client = NetisClient(
        session=async_get_clientsession(hass),
        host=host,
        password=password,
    )
    try:
        await client.login()
        await client.get_system_info()
    except NetisAuthError:
        return "invalid_auth"
    except NetisConnectionError:
        return "cannot_connect"
    except NetisError:
        return "unknown"
    return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Netis Router.

    Inherits from ``config_entries.ConfigFlow`` with ``domain=DOMAIN`` so HA
    automatically registers this flow for the "netis" integration.
    """

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlowHandler":
        """Return the options flow handler for adjusting settings post-setup."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user setup step.

        On first call (``user_input is None``) shows the setup form.
        On subsequent call (form submitted) validates the connection and
        either creates the config entry or re-shows the form with errors.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            # Use the host IP as the unique ID to prevent duplicate entries.
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Attempt a live connection test before saving credentials.
            error = await _test_connection(
                self.hass,
                host,
                user_input[CONF_PASSWORD],
            )
            if error is None:
                return self.async_create_entry(
                    title=f"Netis {host}",
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Allow adjusting the polling interval after initial setup.

    Accessible via the integration's "Configure" button in HA UI.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Store the config entry for reading current options."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options form (polling interval slider)."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.options.get(
                            "scan_interval", 30
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                }
            ),
        )
