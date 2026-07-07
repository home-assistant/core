"""Config flow for the STIEBEL ELTRON integration."""

import logging
from typing import Any, override

from pystiebeleltron import StiebelEltronModbusError, get_controller_model
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def check_controller_model(host: str, port: int) -> str | None:
    """Check if the controller model is valid."""
    try:
        await get_controller_model(host, port)
    except StiebelEltronModbusError:
        _LOGGER.debug("Cannot connect to Stiebel Eltron device", exc_info=True)
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown"
    return None


class StiebelEltronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for STIEBEL ELTRON."""

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
            error = await check_controller_model(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )
            if error is not None:
                errors["base"] = error
            else:
                return self.async_create_entry(title="Stiebel Eltron", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        config_entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            error = await check_controller_model(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )
            if error is not None:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    config_entry,
                    reason="reconfigure_successful",
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
vol.Required(CONF_HOST, default=config_entry.data[CONF_HOST]): str,
                    vol.Required(
                        CONF_PORT,
                        default=config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                    ): int,
                }
            ),
            errors=errors,
        )
