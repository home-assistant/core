"""Config flow for ViCare integration."""
from __future__ import annotations

import logging
from typing import Any

from PyViCare.PyViCareUtils import PyViCareInvalidCredentialsError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.dhcp import MAC_ADDRESS
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from . import vicare_login
from .const import (
    CONF_CIRCUIT,
    CONF_HEATING_TYPE,
    DEFAULT_HEATING_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ViCare."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Invoke when a user initiates a flow via the user interface."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        data_schema = {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(CONF_CLIENT_ID): cv.string,
            vol.Required(CONF_HEATING_TYPE, default=DEFAULT_HEATING_TYPE.value): vol.In(
                [e.value for e in HeatingType]
            ),
            vol.Optional(CONF_NAME, default="ViCare"): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=30)
            ),
        }
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    vicare_login, self.hass, user_input
                )
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except PyViCareInvalidCredentialsError as ex:
                _LOGGER.debug("Could not log in to ViCare, %s", ex)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info):
        """Invoke when a Viessmann MAC address is discovered on the network."""
        formatted_mac = format_mac(discovery_info[MAC_ADDRESS])
        _LOGGER.info("Found device with mac %s", formatted_mac)

        await self.async_set_unique_id(formatted_mac)
        self._abort_if_unique_id_configured()

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user()

    async def async_step_import(self, import_info):
        """Handle a flow initiated by a YAML config import."""

        await self.async_set_unique_id("Configuration.yaml")
        self._abort_if_unique_id_configured()

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Remove now unsupported config parameters
        if import_info.get(CONF_CIRCUIT):
            import_info.pop(CONF_CIRCUIT)

        # Add former optional config if missing
        if import_info.get(CONF_HEATING_TYPE) is None:
            import_info[CONF_HEATING_TYPE] = DEFAULT_HEATING_TYPE.value

        return self.async_create_entry(
            title="Configuration.yaml",
            data=import_info,
        )
