"""Config flow for the Seko Pooldose integration."""

from __future__ import annotations

import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_handler import RequestHandler, RequestStatus
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_INCLUDE_SENSITIVE_DATA,
    CONF_SERIALNUMBER,
    DEFAULT_HOST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_INCLUDE_SENSITIVE_DATA, default=False): cv.boolean,
    }
)


class PooldoseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seko Pooldose."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        error_placeholders = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            include_sensitive = user_input[CONF_INCLUDE_SENSITIVE_DATA]

            # test connection to host
            status, handler = await RequestHandler.create(host, 5)
            if status == RequestStatus.HOST_UNREACHABLE:
                errors["base"] = "cannot_connect"
            elif status == RequestStatus.PARAMS_FETCH_FAILED:
                errors["base"] = "parama_fetch_failed"
            else:  # SUCCESS
                _LOGGER.debug("Connected to device at %s", host)
                # Check API version
                api_status, api_versions = handler.check_apiversion_supported()
                if api_status == RequestStatus.NO_DATA:
                    errors["base"] = "api_not_set"
                elif api_status == RequestStatus.API_VERSION_UNSUPPORTED:
                    errors["base"] = "api_not_supported"
                    error_placeholders = api_versions
                else:  # SUCCESS
                    client_status, client = await PooldoseClient.create(
                        host, 5, include_sensitive
                    )
                    if client_status != RequestStatus.SUCCESS:
                        # All cases handled by RequestHandler before
                        errors["base"] = "cannot_connect"
                    else:  # SUCCESS
                        serial_number = client.device_info.get("SERIAL_NUMBER")
                        await self.async_set_unique_id(serial_number)
                        self._abort_if_unique_id_configured()
                        entry_data = {
                            CONF_HOST: host,
                            CONF_SERIALNUMBER: serial_number,
                            CONF_INCLUDE_SENSITIVE_DATA: include_sensitive,
                        }
                        return self.async_create_entry(
                            title=f"PoolDose {serial_number}", data=entry_data
                        )

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA_DEVICE,
            errors=errors,
            description_placeholders=error_placeholders,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler for Pooldose."""
        return PooldoseOptionsFlowHandler(config_entry)


class PooldoseOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle (re-)configuration after initial setup."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize the Pooldose options flow handler."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options form."""
        errors: dict[str, str] = {}
        error_placeholders = None
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_SCAN_INTERVAL: self.entry.options.get(
                CONF_SCAN_INTERVAL,
                self.entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ),
            CONF_TIMEOUT: self.entry.options.get(
                CONF_TIMEOUT,
                self.entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ),
            CONF_INCLUDE_SENSITIVE_DATA: self.entry.options.get(
                CONF_INCLUDE_SENSITIVE_DATA,
                self.entry.data.get(CONF_INCLUDE_SENSITIVE_DATA, False),
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
                    ): cv.positive_int,
                    vol.Required(
                        CONF_TIMEOUT, default=defaults[CONF_TIMEOUT]
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_INCLUDE_SENSITIVE_DATA,
                        default=defaults[CONF_INCLUDE_SENSITIVE_DATA],
                    ): cv.boolean,
                }
            ),
            errors=errors,
            description_placeholders=error_placeholders,
        )
