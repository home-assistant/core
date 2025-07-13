"""Config flow for the Seko Pooldose integration."""

from __future__ import annotations

import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_handler import RequestHandler, RequestStatus
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import CONF_SERIALNUMBER, DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
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

            # Test connection to host
            status, handler = await RequestHandler.create(host)
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
                    # Use the factory method to create client
                    client_status, client = await PooldoseClient.create(host)
                    if client_status != RequestStatus.SUCCESS:
                        errors["base"] = "cannot_connect"
                    else:  # SUCCESS
                        serial_number = client.device_info.get("SERIAL_NUMBER")
                        await self.async_set_unique_id(serial_number)
                        self._abort_if_unique_id_configured()
                        entry_data = {
                            CONF_HOST: host,
                            CONF_SERIALNUMBER: serial_number,
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
