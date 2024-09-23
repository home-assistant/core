"""Config flow for Dexcom integration."""

from __future__ import annotations

from typing import Any

from pydexcom import AccountError, Dexcom, SessionError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_UNIT_OF_MEASUREMENT, CONF_USERNAME
from homeassistant.core import callback

from .const import CONF_SERVER, DOMAIN, MG_DL, MMOL_L, SERVER_OUS, SERVER_US

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SERVER): vol.In({SERVER_US, SERVER_OUS}),
    }
)


class DexcomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dexcom."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    Dexcom,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_SERVER] == SERVER_OUS,
                )
            except SessionError:
                errors["base"] = "cannot_connect"
            except AccountError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> DexcomOptionsFlowHandler:
        """Get the options flow for this handler."""
        return DexcomOptionsFlowHandler(config_entry)


class DexcomOptionsFlowHandler(OptionsFlow):
    """Handle a option flow for Dexcom."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UNIT_OF_MEASUREMENT,
                    default=self.config_entry.options.get(
                        CONF_UNIT_OF_MEASUREMENT, MG_DL
                    ),
                ): vol.In({MG_DL, MMOL_L}),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
