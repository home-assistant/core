"""Adds config flow for wsdot."""

import logging
from typing import Any

from aiohttp.client_exceptions import ClientError
import voluptuous as vol
import wsdot as wsdot_api

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult

from .sensor import CONF_API_KEY, CONF_TRAVEL_TIMES, DOMAIN

DIALOG_API_KEY = "API Key"
DIALOG_NAME = "Name"
CONF_TITLE = "title"
CONF_DATA = "data"

_LOGGER = logging.getLogger(__name__)


class InvalidApiKeyError(ClientError):
    """Exception indicating the user entered an invalid API Key."""


class WSDOTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for WSDOT."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                wsdot_travel_times = wsdot_api.WsdotTravelTimes(
                    user_input[DIALOG_API_KEY]
                )
                travel_time_routes = await wsdot_travel_times.get_all_travel_times()
            except wsdot_api.WsdotTravelError as ws_error:
                if ws_error.status == 400:
                    errors[DIALOG_API_KEY] = (
                        "Invalid API Key. If you do not have an API Key, you can get a new one at https://wsdot.wa.gov/traffic/api/"
                    )
                else:
                    err_msg = "Unable to retrieve routes from WSDOT"
                    _LOGGER.exception(err_msg)
                    errors["base"] = err_msg
            else:
                return self.async_create_entry(
                    title=user_input[DIALOG_NAME],
                    data={
                        CONF_API_KEY: user_input[DIALOG_API_KEY],
                        CONF_TRAVEL_TIMES: [
                            {"id": t.TravelTimeID, "name": t.Name}
                            for t in travel_time_routes
                        ],
                    },
                )

        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=vol.Schema(
                {
                    vol.Required(DIALOG_API_KEY): str,
                    vol.Optional(DIALOG_NAME, default=DOMAIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initialized by import."""
        return self.async_create_entry(
            title=DOMAIN,
            data={
                CONF_API_KEY: import_info[CONF_API_KEY],
                CONF_TRAVEL_TIMES: import_info[CONF_TRAVEL_TIMES],
            },
        )
