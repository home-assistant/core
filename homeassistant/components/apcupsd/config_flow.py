"""Config flow for APCUPSd integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import DOMAIN, APCUPSdCoordinator

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

        host, port = user_input[CONF_HOST], user_input[CONF_PORT]

        # Abort if an entry with same host and port is present.
        self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

        # Test the connection to the host and get the current status for serial number.
        coordinator = APCUPSdCoordinator(self.hass, host, port)
        await coordinator.async_request_refresh()

        if isinstance(coordinator.last_exception, (UpdateFailed, TimeoutError)):
            errors = {"base": "cannot_connect"}
            return self.async_show_form(
                step_id="user", data_schema=_SCHEMA, errors=errors
            )

        if not coordinator.data:
            return self.async_abort(reason="no_status")

        # We _try_ to use the serial number of the UPS as the unique id since this field
        # is not guaranteed to exist on all APC UPS models.
        await self.async_set_unique_id(coordinator.ups_serial_no)
        self._abort_if_unique_id_configured()

        title = "APC UPS"
        if coordinator.ups_name is not None:
            title = coordinator.ups_name
        elif coordinator.ups_model is not None:
            title = coordinator.ups_model
        elif coordinator.ups_serial_no is not None:
            title = coordinator.ups_serial_no

        return self.async_create_entry(
            title=title,
            data=user_input,
        )
