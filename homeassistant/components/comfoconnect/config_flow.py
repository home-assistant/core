"""Config flow for ComfoConnect."""

from typing import Any

from pycomfoconnect import Bridge
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_TOKEN

from .const import (
    CONF_USER_AGENT,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN): str,
        vol.Optional(CONF_PIN, default=DEFAULT_PIN): int,
        vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): str,
    }
)


class ComfoConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ComfoConnect."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if len(user_input[CONF_TOKEN]) != 32:
                errors[CONF_TOKEN] = "invalid_token"
            else:
                bridges = Bridge.discover(user_input[CONF_HOST])
                if not bridges:
                    errors["base"] = "cannot_connect"
                else:
                    bridge = bridges[0]
                    await self.async_set_unique_id(bridge.uuid.hex())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Comfoconnect", data=user_input
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA,
                {
                    CONF_TOKEN: DEFAULT_TOKEN,
                    CONF_PIN: DEFAULT_PIN,
                    CONF_USER_AGENT: DEFAULT_USER_AGENT,
                },
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry."""
        bridges = Bridge.discover(import_info[CONF_HOST])
        if not bridges:
            return self.async_abort(reason="cannot_connect")
        bridge = bridges[0]
        await self.async_set_unique_id(bridge.uuid.hex())
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Comfoconnect",
            data={
                CONF_HOST: import_info[CONF_HOST],
                CONF_TOKEN: import_info[CONF_TOKEN],
                CONF_PIN: import_info[CONF_PIN],
                CONF_USER_AGENT: import_info[CONF_USER_AGENT],
            },
        )
