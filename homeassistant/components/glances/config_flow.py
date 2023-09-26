"""Config flow for Glances."""
from __future__ import annotations

from typing import Any

from glances_api.exceptions import (
    GlancesApiAuthorizationError,
    GlancesApiConnectionError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult

from . import get_api
from .const import (
    CONF_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_VERSION,
    DOMAIN,
    SUPPORTED_VERSIONS,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_VERSION, default=DEFAULT_VERSION): vol.In(SUPPORTED_VERSIONS),
        vol.Optional(CONF_SSL, default=False): bool,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    }
)


class GlancesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Glances config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            api = get_api(self.hass, user_input)
            try:
                await api.get_ha_sensor_data()
            except GlancesApiAuthorizationError:
                errors["base"] = "invalid_auth"
            except GlancesApiConnectionError:
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
