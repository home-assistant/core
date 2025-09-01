"""Config flow for Met Office integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import datapoint
from datapoint.exceptions import APIException
import datapoint.Manager
from requests import HTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant, latitude: float, longitude: float, api_key: str
) -> dict[str, Any]:
    """Validate that the user input allows us to connect to DataPoint.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    errors = {}
    connection = datapoint.Manager.Manager(api_key=api_key)

    try:
        forecast = await hass.async_add_executor_job(
            connection.get_forecast,
            latitude,
            longitude,
            "daily",
            False,
        )

    except (HTTPError, APIException) as err:
        if isinstance(err, HTTPError) and err.response.status_code == 401:
            errors["base"] = "invalid_auth"
        else:
            errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        return {"site_name": forecast.name, "errors": errors}

    return {"errors": errors}


class MetOfficeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Met Office weather integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}_{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            result = await validate_input(
                self.hass,
                latitude=user_input[CONF_LATITUDE],
                longitude=user_input[CONF_LONGITUDE],
                api_key=user_input[CONF_API_KEY],
            )

            errors = result["errors"]

            if not errors:
                user_input[CONF_NAME] = result["site_name"]
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            },
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}

        entry = self._get_reauth_entry()
        if user_input is not None:
            result = await validate_input(
                self.hass,
                latitude=entry.data[CONF_LATITUDE],
                longitude=entry.data[CONF_LONGITUDE],
                api_key=user_input[CONF_API_KEY],
            )

            errors = result["errors"]

            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            description_placeholders={
                "docs_url": ("https://www.home-assistant.io/integrations/metoffice")
            },
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
