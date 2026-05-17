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
            try:
                device_id = await self._async_validate_host(user_input[CONF_HOST])
            except (
                ZendureP1ConnectionError,
                ZendureP1ResponseError,
                ZendureP1TimeoutError,
            ) as err:
                LOGGER.debug("Cannot connect to Zendure P1: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                LOGGER.exception(
                    "Unexpected error while connecting to Zendure P1: %s", err
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_id,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _async_validate_host(self, host: str) -> str:
        """Validate host by connecting and return the device ID."""
        async with ZendureP1Client(host) as client:
            report = await client.get_report()
        return report.device_id
