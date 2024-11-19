"""Config flow for the Niko home control integration."""

from __future__ import annotations

from nikohomecontrol import NikoHomeControlConnection
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DEFAULT_IP, DEFAULT_PORT, DOMAIN
from .errors import CannotConnect

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_IP): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> None:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]

    try:
        controller = NikoHomeControlConnection(host, port)
    except Exception as e:
        raise CannotConnect("cannot_connect") from e

    if not controller:
        raise CannotConnect("cannot_connect")


class NikoHomeControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Niko Home Control."""

    VERSION = 1

    def __init__(self, import_info: dict[str, str] | None = None) -> None:
        """Initialize the config flow."""
        self._import_info = import_info

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        DATA_SCHEMA.schema.update(self._import_info) if self._import_info else None

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                if self._import_info is not None:
                    return self.async_abort(reason="import_failed")
                errors["base"] = "cannot_connect"

            return self.async_create_entry(
                title=DOMAIN,
                data=user_input,
            )

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_info: dict[str, str]) -> ConfigFlowResult:
        """Import a config entry."""
        if import_info is not None:
            self._import_info = import_info

        return await self.async_step_user(None)
