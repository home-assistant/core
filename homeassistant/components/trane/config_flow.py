"""Config flow for the Trane Local integration."""

from __future__ import annotations

import logging
from typing import Any

from steamloop import PairingError, SteamloopConnectionError, ThermostatConnection
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import CONF_SECRET_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class TraneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trane Local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            self._async_abort_entries_match({CONF_HOST: host})
            conn = ThermostatConnection(host, secret_key="")
            try:
                await conn.connect()
                await conn.pair()
            except SteamloopConnectionError, PairingError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during pairing")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Thermostat ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_SECRET_KEY: conn.secret_key,
                    },
                )
            finally:
                await conn.disconnect()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
