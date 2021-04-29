"""Config flow for ClimaCell integration."""
from __future__ import annotations

import logging
from typing import Any

from pyclimacell import ClimaCellV3
from pyclimacell.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
)
from pyclimacell.pyclimacell import ClimaCellV4
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CC_ATTR_TEMPERATURE,
    CC_V3_ATTR_TEMPERATURE,
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_config_schema(
    hass: core.HomeAssistant, input_dict: dict[str, Any] = None
) -> vol.Schema:
    """
    Return schema defaults for init step based on user input/config dict.

    Retain info already provided for future form views by setting them as
    defaults in schema.
    """
    if input_dict is None:
        input_dict = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=input_dict.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(CONF_API_KEY, default=input_dict.get(CONF_API_KEY)): str,
            vol.Required(CONF_API_VERSION, default=4): vol.In([3, 4]),
            vol.Inclusive(
                CONF_LATITUDE,
                "location",
                default=input_dict.get(CONF_LATITUDE, hass.config.latitude),
            ): cv.latitude,
            vol.Inclusive(
                CONF_LONGITUDE,
                "location",
                default=input_dict.get(CONF_LONGITUDE, hass.config.longitude),
            ): cv.longitude,
        },
        extra=vol.REMOVE_EXTRA,
    )


def _get_unique_id(hass: HomeAssistant, input_dict: dict[str, Any]):
    """Return unique ID from config data."""
    return (
        f"{input_dict[CONF_API_KEY]}"
        f"_{input_dict.get(CONF_LATITUDE, hass.config.latitude)}"
        f"_{input_dict.get(CONF_LONGITUDE, hass.config.longitude)}"
    )


class ClimaCellOptionsConfigFlow(config_entries.OptionsFlow):
    """Handle ClimaCell options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize ClimaCell options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Manage the ClimaCell options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = {
            vol.Required(
                CONF_TIMESTEP,
                default=self._config_entry.options.get(CONF_TIMESTEP, DEFAULT_TIMESTEP),
            ): vol.In([1, 5, 15, 30]),
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema)
        )


class ClimaCellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ClimaCell Weather API."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ClimaCellOptionsConfigFlow:
        """Get the options flow for this handler."""
        return ClimaCellOptionsConfigFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                unique_id=_get_unique_id(self.hass, user_input)
            )
            self._abort_if_unique_id_configured()

            try:
                if user_input[CONF_API_VERSION] == 3:
                    api_class = ClimaCellV3
                    field = CC_V3_ATTR_TEMPERATURE
                else:
                    api_class = ClimaCellV4
                    field = CC_ATTR_TEMPERATURE
                await api_class(
                    user_input[CONF_API_KEY],
                    str(user_input.get(CONF_LATITUDE, self.hass.config.latitude)),
                    str(user_input.get(CONF_LONGITUDE, self.hass.config.longitude)),
                    session=async_get_clientsession(self.hass),
                ).realtime([field])

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except CantConnectException:
                errors["base"] = "cannot_connect"
            except InvalidAPIKeyException:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RateLimitedException:
                errors[CONF_API_KEY] = "rate_limited"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=_get_config_schema(self.hass, user_input),
            errors=errors,
        )
