"""Config flow for APCUPSd integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, APCUPSdData

_LOGGER = logging.getLogger(__name__)

_PORT_SELECTOR = vol.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=65535, mode=selector.NumberSelectorMode.BOX
        ),
    ),
    vol.Coerce(int),
)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """APCUPSd integration config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="localhost"): cv.string,
                vol.Required(CONF_PORT, default=3551): _PORT_SELECTOR,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=schema)

        # Test the connection to the hostand get the current status for serial number.
        data_service = APCUPSdData(user_input[CONF_HOST], user_input[CONF_PORT])
        try:
            await self.hass.async_add_executor_job(data_service.update)
        except OSError:
            errors = {"base": "cannot_connect"}
            return self.async_show_form(
                step_id="user", data_schema=schema, errors=errors
            )

        if len(data_service.status) == 0:
            return self.async_abort(reason="no_status")

        # We _try_ to use the serial number of the UPS as the unique id since
        # this field is not guaranteed to exist on all APC UPS models.
        await self.async_set_unique_id(data_service.serial_no)
        self._abort_if_unique_id_configured()

        # APCNAME or MODEL fields are not always available on all UPS models, here we
        # try to assign a friendly title for the integration using those fields, but
        # default to a generic "APC UPS" name.
        if (name := data_service.name) is not None:
            title = name
        elif (model := data_service.model) is not None:
            title = model
        else:
            title = "APC UPS"

        return self.async_create_entry(
            title=title,
            description="APCUPSd",
            data=user_input,
        )

    async def async_step_import(self, conf: dict[str, Any]) -> FlowResult:
        """Import a configuration from yaml configuration."""
        # If we are importing from YAML configuration, user_input could contain a
        # CONF_RESOURCES with a list of resources (sensors) to be enabled.
        return await self.async_step_user(user_input=conf)
