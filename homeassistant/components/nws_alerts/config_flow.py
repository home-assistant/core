"""Config flow for NWS Alerts integration."""
from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import API_ENDPOINT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("api_key"): str,
        vol.Required("friendly_name", default="NWS Alerts"): str,
        vol.Required("update_interval", default=90): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect.

    Return the user input (modified if necessary) or raise a vol.Invalid
    exception if the data is incorrect.
    """
    endpoint = API_ENDPOINT.format(
        lat=data["lat"], lon=data["lon"], api_key=data["api_key"]
    )
    try:
        response = await hass.async_add_executor_job(requests.get, endpoint)
    except requests.exceptions.HTTPError as error:
        _LOGGER.error("Error connecting to NWS Alerts API: %s", error)
        raise CannotConnect(
            "Cannot connect to alerts API. Please try again later"
        ) from error
    except requests.exceptions.RequestException as error:
        _LOGGER.error("Error connecting to NWS Alerts API: %s", error)
        raise CannotConnect(
            "Cannot connect to alerts API. Please try again later"
        ) from error

    # check if it didn't return code 401
    if response.status_code == 401:
        _LOGGER.error("Invalid API key")
        raise Error401("Invalid API key")

    if response.status_code == 404:
        _LOGGER.error("Invalid location")
        raise Error404("Invalid location")

    if response.status_code == 429:
        _LOGGER.error("Too many requests")
        raise Error429("Too many requests")

    if (
        response.status_code == 500
        or response.status_code == 502
        or response.status_code == 503
        or response.status_code == 504
    ):
        _LOGGER.error("Service Unavailable")
        raise Error5XX("Service Unavailable")

    if response.status_code == 200:
        return data
    else:
        raise Exception("Unknown error")


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NWS Alerts."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        lat = self.hass.config.latitude
        lon = self.hass.config.longitude
        schema = STEP_USER_DATA_SCHEMA.extend(
            {
                vol.Required("lat", default=lat): float,
                vol.Required("lon", default=lon): float,
            }
        )
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=schema,
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Error401:
            errors["api_key"] = "error_401"
        except Error404:
            errors["lat"] = "error_404"
            errors["lon"] = "error_404"
        except Error429:
            errors["base"] = "error_429"
        except Error5XX:
            errors["base"] = "error_5XX"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=user_input["friendly_name"], data=user_input
            )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class Error401(HomeAssistantError):
    """Error to indicate error 401."""


class Error404(HomeAssistantError):
    """Error to indicate error 404."""


class Error429(HomeAssistantError):
    """Error to indicate error 429."""


class Error5XX(HomeAssistantError):
    """Error to indicate error 5XX."""
