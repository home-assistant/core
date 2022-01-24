"""Config flow for APCUPSd integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_RESOURCES
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, APCUPSdData
from .sensor import SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """APCUPSd integration config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Test if connection to the host is ok and get the current status for later configuration.
            data_service = APCUPSdData(user_input[CONF_HOST], user_input[CONF_PORT])
            try:
                status: dict[str, Any] | None = await self.hass.async_add_executor_job(
                    lambda: data_service.status
                )
                if status is None:
                    return self.async_abort(reason="no_status")

                # We _try_ to use the serial number of the UPS as the unique id since this field is not guaranteed to
                # exist on all APC UPS models.
                if "SERIALNO" in status:
                    await self.async_set_unique_id(status["SERIALNO"])
                    self._abort_if_unique_id_configured()

                # Since the MODEL field is not always available on all models, we try to find a friendly name for the
                # integration, otherwise default to "APC UPS".
                return self.async_create_entry(
                    title=status.get("MODEL", "APC UPS"),
                    description="APCUPSd",
                    data=user_input,
                )
            except OSError:
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="localhost"): cv.string,
                vol.Required(CONF_PORT, default=3551): cv.port,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class OptionsFlowHandler(OptionsFlow):
    """Handles options flow for APCUPSd."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the options for APCUPSd."""

        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        data_service: APCUPSdData = self.hass.data[DOMAIN][self.config_entry.entry_id]

        # We try to get current user-specified resources and use all available resources as default.
        available_resources = list(data_service.status.keys())
        current = self.config_entry.options.get(CONF_RESOURCES, available_resources)

        # Create a resource -> sensor friendly name mapping to display as description for each resource.
        sensor_names = {
            sensor.key.upper(): f"{sensor.name} ({sensor.key.upper()})"
            for sensor in SENSOR_TYPES
        }

        # For some models the underlying apcaccess library will return undocumented fields, for those fields we give
        # an Unknown description.
        for resource in available_resources:
            if resource not in sensor_names:
                sensor_names[resource] = f"Unknown ({resource})"

        # Sort the available resource list based on their description for better user experience.
        available_resources = sorted(available_resources, key=lambda k: sensor_names[k])

        schema = vol.Schema(
            {
                vol.Optional(CONF_RESOURCES, default=current): cv.multi_select(
                    {
                        resource: sensor_names[resource]
                        for resource in available_resources
                    }
                )
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
