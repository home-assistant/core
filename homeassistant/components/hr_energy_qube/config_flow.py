"""Config flow for Qube Heat Pump integration."""

from __future__ import annotations

from typing import Any

from python_qube_heatpump import QubeClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN


class QubeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qube Heat Pump."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            self._async_abort_entries_match({CONF_HOST: host})

            # Connect and verify it's a Qube by reading software version
            client = QubeClient(host, DEFAULT_PORT)
            try:
                connected = await client.connect()
                if not connected:
                    errors["base"] = "cannot_connect"
                else:
                    version = await client.async_get_software_version()
                    if version is None:
                        errors["base"] = "not_qube_device"
            except OSError, TimeoutError:
                errors["base"] = "cannot_connect"
            finally:
                await client.close()

            if not errors:
                return self.async_create_entry(
                    title="Qube heat pump",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: DEFAULT_PORT,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
