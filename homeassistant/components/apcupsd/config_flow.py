"""Config flow for APCUPSd integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    SOURCE_IMPORT,
    ConfigFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_RESOURCES
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

        # Test if connection to the host is ok and get the current status for later
        # configurations.
        data_service = APCUPSdData(user_input[CONF_HOST], user_input[CONF_PORT])
        try:
            await self.hass.async_add_executor_job(data_service.update)
            status = data_service.status
        except OSError:
            errors = {"base": "cannot_connect"}
            return self.async_show_form(
                step_id="user", data_schema=schema, errors=errors
            )

        if status is None or len(status) == 0:
            return self.async_abort(reason="no_status")

        # We _try_ to use the serial number of the UPS as the unique id since
        # this field is not guaranteed to exist on all APC UPS models.
        if "SERIALNO" in status:
            await self.async_set_unique_id(status["SERIALNO"])
            self._abort_if_unique_id_configured()

        data = {
            CONF_HOST: user_input[CONF_HOST],
            CONF_PORT: user_input[CONF_PORT],
        }

        # If we are importing from YAML configuration, user_input may contain a
        # CONF_RESOURCES with a list of resources (sensors) to be enabled.
        if self.source == SOURCE_IMPORT and CONF_RESOURCES in user_input:
            data[CONF_RESOURCES] = user_input[CONF_RESOURCES]

        return self.async_create_entry(
            # Since the MODEL field is not always available on all models, we
            # try to set a friendly name for the integration, otherwise default
            # to "APC UPS".
            title=status.get("MODEL", "APC UPS"),
            description="APCUPSd",
            data=data,
        )

    async def async_step_import(self, conf: dict[str, Any]) -> FlowResult:
        """Import a configuration from yaml configuration."""
        return await self.async_step_user(user_input=conf)
