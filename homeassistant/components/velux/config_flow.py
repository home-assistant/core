"""Config flow for Velux integration."""
from typing import Any

from pyvlx import PyVLX, PyVLXException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import _LOGGER, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NINA."""

    VERSION: int = 1

    @staticmethod
    async def test_connection(host: str, password: str):
        """Test the connection to Velux."""
        pyvlx = PyVLX(host=host, password=password)
        await pyvlx.connect()
        await pyvlx.disconnect()

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry."""
        self._async_abort_entries_match({CONF_HOST: config[CONF_HOST]})
        return self.async_create_entry(
            title="VELUX",
            data=config,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None and not errors:
            try:
                await self.test_connection(
                    user_input[CONF_HOST], user_input[CONF_PASSWORD]
                )
            except (PyVLXException, ConnectionError):
                errors["base"] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                return self.async_abort(reason="unknown")
            else:
                return self.async_create_entry(
                    title="VELUX",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            errors=errors,
        )
