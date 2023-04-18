"""Config flow for APCUPSd integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, APCUPSdData

_PORT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=65535, mode=selector.NumberSelectorMode.BOX
        ),
    ),
    vol.Coerce(int),
)

_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="localhost"): cv.string,
        vol.Required(CONF_PORT, default=3551): _PORT_SELECTOR,
    }
)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """APCUPSd integration config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_SCHEMA)

        # Abort if an entry with same host and port is present.
        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )

        # Test the connection to the host and get the current status for serial number.
        data_service = APCUPSdData(user_input[CONF_HOST], user_input[CONF_PORT])
        try:
            await self.hass.async_add_executor_job(data_service.update)
        except OSError:
            errors = {"base": "cannot_connect"}
            return self.async_show_form(
                step_id="user", data_schema=_SCHEMA, errors=errors
            )

        if not data_service.status:
            return self.async_abort(reason="no_status")

        # We _try_ to use the serial number of the UPS as the unique id since this field
        # is not guaranteed to exist on all APC UPS models.
        await self.async_set_unique_id(data_service.serial_no)
        self._abort_if_unique_id_configured()

        title = "APC UPS"
        if data_service.name is not None:
            title = data_service.name
        elif data_service.model is not None:
            title = data_service.model
        elif data_service.serial_no is not None:
            title = data_service.serial_no

        return self.async_create_entry(
            title=title,
            data=user_input,
        )
