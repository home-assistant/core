"""Config flow for gandi_livedns."""
from __future__ import annotations

import logging
from typing import Any

from gandi_api_livedns import GandiApiLiveDNS
from gandi_api_livedns.const import (
    AVAILABLE_TYPE,
    DEFAULT_IPV6,
    DEFAULT_TTL,
    DEFAULT_TYPE,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_TTL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_FQDN,
    CONF_IPV6,
    CONF_RRNAME,
    CONF_RRTYPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

REQUIRED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_FQDN): cv.string,
        vol.Required(CONF_RRNAME): cv.string,
        vol.Required(CONF_RRTYPE, default=DEFAULT_TYPE): vol.In(AVAILABLE_TYPE),
        vol.Required(CONF_TTL, default=DEFAULT_TTL): cv.positive_int,
        vol.Required(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
    }
)


class GandiLiveDnsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gandi.net live DNS."""

    VERSION = 1

    async def _validate_input(self, data: dict):
        """Validate the user input allows us to connect.

        Data has the keys from DATA_SCHEMA with values provided by the user.
        """

        errors = {}
        info = {}

        gandiApiLiveDNS = GandiApiLiveDNS(
            api_key=data[CONF_API_KEY],
            domain=data[CONF_FQDN],
            rrname=data[CONF_RRNAME],
            rrtype=data[CONF_RRTYPE],
            rrttl=data[CONF_TTL],
            ipv6=data[CONF_IPV6],
            logger=_LOGGER,
        )

        record, error = await self.hass.async_add_executor_job(
            gandiApiLiveDNS.getDNSRecord
        )
        if error:
            errors["base"] = error
            _LOGGER.debug(errors["base"])
        else:
            info["record"] = record

        return info, errors

    def __init__(self):
        """Initialize the Gandi.net live DNS config flow."""
        self._config = {}

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initiated by the user."""

        errors = {}

        if user_input is not None:
            record, errors = await self._validate_input(user_input)

            if not errors:
                self._config.update(user_input)

                title = (
                    self._config[CONF_RRTYPE]
                    + ":"
                    + self._config[CONF_RRNAME]
                    + "."
                    + self._config[CONF_FQDN]
                )

                await self.async_set_unique_id(title)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=title, data=self._config)

        return self.async_show_form(
            step_id="user", data_schema=REQUIRED_SCHEMA, errors=errors
        )

    async def _async_validate_or_error(self, config):
        errors = {}
        info = {}

        record, error = await self._validate_input(config)

        if error is not None:
            errors["base"] = error
            _LOGGER.debug(errors["base"])
        else:
            info["record"] = record

        return info, errors

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for Gandi.net live DNS."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize Gandi.net live DNS options flow."""
        self.config_entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): cv.positive_int
                }
            ),
        )
