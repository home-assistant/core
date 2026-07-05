"""Config flow for the nx584 integration."""

import logging
from typing import Any, override

from nx584 import client
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def _async_validate_connection(hass: HomeAssistant, host: str, port: int) -> None:
    """Raise requests.exceptions.ConnectionError if the panel can't be reached."""
    alarm_client = client.Client(f"http://{host}:{port}")
    await hass.async_add_executor_job(alarm_client.list_zones)


class NX584ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for nx584."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                await _async_validate_connection(
                    self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except requests.exceptions.ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import nx584 config from configuration.yaml."""
        host: str = import_config[CONF_HOST]
        port: int = import_config[CONF_PORT]

        self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

        try:
            await _async_validate_connection(self.hass, host, port)
        except requests.exceptions.ConnectionError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=host, data={CONF_HOST: host, CONF_PORT: port}
        )
