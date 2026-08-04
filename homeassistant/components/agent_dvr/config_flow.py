"""Config flow to configure Agent DVR devices."""

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AgentDVRAuthError,
    AgentDVRClient,
    AgentDVRConnectionError,
    AgentDVRError,
)
from .const import DEFAULT_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_SSL, default=False): bool,
    }
)


class AgentDVRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Agent DVR config flow."""

    VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = AgentDVRClient(
                session,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
                user_input.get(CONF_SSL, False),
            )
            try:
                status = await client.get_status()
            except AgentDVRAuthError:
                errors["base"] = "invalid_auth"
            except AgentDVRConnectionError:
                errors["base"] = "cannot_connect"
            except AgentDVRError:
                errors["base"] = "unknown"
            else:
                unique_id = status.get("unique")
                if unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                title = status.get("name") or user_input[CONF_HOST]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
