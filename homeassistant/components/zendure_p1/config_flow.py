"""Config flow for the Zendure Smart Meter P1 integration."""

from typing import Any

import voluptuous as vol
from zendure_p1 import (
    ZendureP1Client,
    ZendureP1ConnectionError,
    ZendureP1ResponseError,
    ZendureP1TimeoutError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


class ZendureP1ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zendure Smart Meter P1."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = await self._async_try_connect(user_input[CONF_HOST], errors)
            if device_id is not None:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_id,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration to update the host."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            device_id = await self._async_try_connect(user_input[CONF_HOST], errors)
            if device_id is not None:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: user_input[CONF_HOST]},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                reconfigure_entry.data,
            ),
            errors=errors,
        )

    async def _async_try_connect(self, host: str, errors: dict[str, str]) -> str | None:
        """Try connecting to the device and return the device ID, or None on failure."""
        try:
            return await self._async_validate_host(host)
        except (
            ZendureP1ConnectionError,
            ZendureP1ResponseError,
            ZendureP1TimeoutError,
        ) as err:
            LOGGER.debug("Cannot connect to Zendure P1: %s", err)
            errors["base"] = "cannot_connect"
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected error while connecting to Zendure P1: %s", err)
            errors["base"] = "unknown"
        return None

    async def _async_validate_host(self, host: str) -> str:
        """Validate host by connecting and return the device ID."""
        async with ZendureP1Client(host) as client:
            report = await client.get_report()
        return report.device_id
