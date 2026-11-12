"""Config flow for the Sharp Aquos TV integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
import sharp_aquos_rc

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv

from .const import CONF_POWER_ON_ENABLED, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Required(CONF_USERNAME): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Required(CONF_USERNAME): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
    }
)


class AquosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sharp Aquos TV."""

    VERSION = 1

    async def _async_validate(self, user_input: Mapping[str, Any]) -> str | None:
        """Try to reach the TV and return an error key on failure."""
        tv = sharp_aquos_rc.TV(
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            15,
            1,
        )
        try:
            await self.hass.async_add_executor_job(tv.info)
        except OSError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if error := await self._async_validate(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the connection settings."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_HOST: entry.data[CONF_HOST], **user_input}
            if error := await self._async_validate(data):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a configuration from YAML."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        return self.async_create_entry(
            title=import_data[CONF_NAME],
            data={
                key: import_data[key]
                for key in (CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD)
            },
            options={CONF_POWER_ON_ENABLED: import_data[CONF_POWER_ON_ENABLED]},
        )
