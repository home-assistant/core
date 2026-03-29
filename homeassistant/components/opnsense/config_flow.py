"""Config flow for OPNsense."""

from __future__ import annotations

from typing import Any

from aioopnsense import OPNsenseApiError, OPNsenseAuthError, OPNsenseClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACES, DOMAIN


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OPNsense."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_URL] = user_input[CONF_URL].rstrip("/")
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

            session = async_get_clientsession(
                self.hass,
                verify_ssl=user_input.get(CONF_VERIFY_SSL, False),
            )
            client = OPNsenseClient(
                url=user_input[CONF_URL],
                api_key=user_input[CONF_API_KEY],
                api_secret=user_input[CONF_API_SECRET],
                session=session,
                verify_ssl=user_input.get(CONF_VERIFY_SSL, False),
            )

            try:
                await client.get_arp()
            except OPNsenseAuthError:
                errors["base"] = "invalid_auth"
            except OPNsenseApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_URL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_API_SECRET): str,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                    vol.Optional(CONF_TRACKER_INTERFACES, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Import OPNsense config from YAML."""
        tracker_interfaces = import_config.get(CONF_TRACKER_INTERFACES, [])
        import_config[CONF_TRACKER_INTERFACES] = ",".join(tracker_interfaces)

        self._async_abort_entries_match({CONF_URL: import_config[CONF_URL]})

        return self.async_create_entry(
            title=import_config[CONF_URL],
            data=import_config,
        )
