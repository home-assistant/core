"""Config flow for Co2signal integration."""
from __future__ import annotations

import logging
from typing import Any

import CO2Signal
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_COUNTRY_CODE, DOMAIN, HOME_LOCATION_NAME, MSG_LOCATION

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Co2signal."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Inclusive(CONF_LATITUDE, "coords", msg=MSG_LOCATION): cv.latitude,
                vol.Inclusive(CONF_LONGITUDE, "coords", msg=MSG_LOCATION): cv.longitude,
                vol.Exclusive(CONF_COUNTRY_CODE, "coords"): cv.string,
                vol.Required(CONF_API_KEY): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors=errors,
            )

        try:
            data = await self.hass.async_add_executor_job(
                CO2Signal.get_latest,
                user_input[CONF_API_KEY],
                user_input.get(CONF_COUNTRY_CODE),
                user_input.get(CONF_LATITUDE),
                user_input.get(CONF_LONGITUDE),
            )
        except ValueError as exp:
            if "Invalid authentication credentials" in str(exp):
                errors["base"] = "invalid_auth"
            else:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if data.get("status") == "ok":
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
