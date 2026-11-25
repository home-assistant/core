"""Config flow for Danfoss Air."""

import logging
from typing import Any, override

import probatio
from pydanfossair.commands import ReadCommand
from pydanfossair.danfossclient import DanfossClient

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN, INTEGRATION_TITLE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})


def _test_connection(host: str) -> str | None:
    """Read a register from the CCM module and return an error key on failure."""
    try:
        DanfossClient(host).command(ReadCommand.exhaustTemperature)
    except OSError:
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error connecting to the Danfoss Air CCM module")
        return "unknown"
    return None


class DanfossAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Danfoss Air."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if error := await self.hass.async_add_executor_job(
                _test_connection, user_input[CONF_HOST]
            ):
                errors["base"] = error
            else:
                return self.async_create_entry(title=INTEGRATION_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the YAML configuration."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        if error := await self.hass.async_add_executor_job(
            _test_connection, import_data[CONF_HOST]
        ):
            return self.async_abort(reason=error)
        return self.async_create_entry(
            title=INTEGRATION_TITLE, data={CONF_HOST: import_data[CONF_HOST]}
        )
