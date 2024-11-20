"""Config flow for the Niko home control integration."""

from __future__ import annotations

from typing import Any

from nikohomecontrol import NikoHomeControlConnection
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_IP, DEFAULT_PORT, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_IP): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)

IDENTIFIER = f"${DOMAIN}.controller"  # only one controller is supported


def test_connection(host: str, port: int) -> str | None:
    """Test if we can connect to the Niko Home Control controller."""
    try:
        if NikoHomeControlConnection(host, port):
            return None
    except Exception:  # noqa: BLE001
        return "unknown"
    else:
        return "cannot_connect"


class NikoHomeControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Niko Home Control."""

    VERSION = 1

    def __init__(self, import_info: dict[str, str] | None = None) -> None:
        """Initialize the config flow."""
        self._import_info = import_info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            error = test_connection(user_input[CONF_HOST], user_input[CONF_PORT])
            if not error:
                await self.async_set_unique_id(IDENTIFIER)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DOMAIN,
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry."""
        error = test_connection(import_info[CONF_HOST], DEFAULT_PORT)

        if not error:
            return self.async_create_entry(
                title=DOMAIN,
                data={CONF_HOST: import_info[CONF_HOST], CONF_PORT: DEFAULT_PORT},
            )
        return self.async_abort(reason=error)
