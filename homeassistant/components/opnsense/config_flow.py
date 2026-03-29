"""Config flow for OPNsense."""

from __future__ import annotations

from typing import Any

import aiohttp
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
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

            session = async_get_clientsession(
                self.hass,
                verify_ssl=user_input.get(CONF_VERIFY_SSL, False),
            )
            url = user_input[CONF_URL].rstrip("/")
            auth = aiohttp.BasicAuth(
                user_input[CONF_API_KEY], user_input[CONF_API_SECRET]
            )

            try:
                async with session.get(
                    f"{url}/diagnostics/interface/get_arp",
                    auth=auth,
                    ssl=user_input.get(CONF_VERIFY_SSL, False),
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    resp.raise_for_status()
            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except (aiohttp.ClientError, TimeoutError):
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
