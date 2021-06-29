"""Config flow for gandi_livedns."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DOMAIN,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_TTL,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    AVAILABLE_TYPE,
    CONF_IPV6,
    CONF_UPDATE_INTERVAL,
    DEFAULT_IPV6,
    DEFAULT_TIMEOUT,
    DEFAULT_TTL,
    DEFAULT_TYPE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .gandi import GandiApiLiveDNS

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): vol.In(AVAILABLE_TYPE),
        vol.Optional(CONF_TTL, default=DEFAULT_TTL): cv.positive_int,
        vol.Optional(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(
            CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
        ): cv.positive_int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    errors = {}
    info = {}

    gandiApiLiveDNS = GandiApiLiveDNS(hass, data, _LOGGER)
    record, error = await gandiApiLiveDNS.getDNSRecord()
    if error:
        errors["base"] = error
        _LOGGER.debug(errors["base"])
    else:
        info["record"] = record

    return info, errors


class GandiLiveDnsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gandi.net live DNS."""

    VERSION = 1

    def __init__(self):
        """Initialize the Gandi.net live DNS config flow."""
        self._config = {}

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initiated by the user."""

        errors = {}

        if user_input is not None:
            record, errors = await validate_input(self.hass, user_input)

            if not errors:
                self._config.update(user_input)

                title = (
                    self._config[CONF_NAME]
                    + self._config[CONF_TYPE]
                    + self._config[CONF_DOMAIN]
                )

                await self.async_set_unique_id(title)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=title, data=self._config)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def _async_validate_or_error(self, config):
        errors = {}
        info = {}

        record, error = await validate_input(self.hass, config)

        if error is not None:
            errors["base"] = error
            _LOGGER.debug(errors["base"])
        else:
            info["record"] = record

        return info, errors
