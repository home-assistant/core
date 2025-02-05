"""Config flow for Monoprice 6-Zone Amplifier integration."""

from __future__ import annotations

import logging
from typing import Any

from pymonoprice import get_monoprice
from serial import SerialException
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_SOURCE_1,
    CONF_SOURCE_2,
    CONF_SOURCE_3,
    CONF_SOURCE_4,
    CONF_SOURCE_5,
    CONF_SOURCE_6,
    CONF_SOURCES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SOURCES = [
    CONF_SOURCE_1,
    CONF_SOURCE_2,
    CONF_SOURCE_3,
    CONF_SOURCE_4,
    CONF_SOURCE_5,
    CONF_SOURCE_6,
]

OPTIONS_FOR_DATA: VolDictType = {vol.Optional(source): str for source in SOURCES}

DATA_SCHEMA = vol.Schema({vol.Required(CONF_PORT): str, **OPTIONS_FOR_DATA})


@callback
def _sources_from_config(data):
    sources_config = {
        str(idx + 1): data.get(source) for idx, source in enumerate(SOURCES)
    }

    return {
        index: name.strip()
        for index, name in sources_config.items()
        if (name is not None and name.strip() != "")
    }


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    try:
        await hass.async_add_executor_job(get_monoprice, data[CONF_PORT])
    except SerialException as err:
        _LOGGER.error("Error connecting to Monoprice controller")
        raise CannotConnect from err

    sources = _sources_from_config(data)

    # Return info that you want to store in the config entry.
    return {CONF_PORT: data[CONF_PORT], CONF_SOURCES: sources}


class MonoPriceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Monoprice 6-Zone Amplifier."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=user_input[CONF_PORT], data=info)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MonopriceOptionsFlowHandler:
        """Define the config flow to handle options."""
        return MonopriceOptionsFlowHandler()


@callback
def _key_for_source(index, source, previous_sources):
    if str(index) in previous_sources:
        key = vol.Optional(
            source, description={"suggested_value": previous_sources[str(index)]}
        )
    else:
        key = vol.Optional(source)

    return key


class MonopriceOptionsFlowHandler(OptionsFlow):
    """Handle a Monoprice options flow."""

    @callback
    def _previous_sources(self):
        if CONF_SOURCES in self.config_entry.options:
            previous = self.config_entry.options[CONF_SOURCES]
        else:
            previous = self.config_entry.data[CONF_SOURCES]

        return previous

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data={CONF_SOURCES: _sources_from_config(user_input)}
            )

        previous_sources = self._previous_sources()

        options = {
            _key_for_source(idx + 1, source, previous_sources): str
            for idx, source in enumerate(SOURCES)
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
