"""Config flow for WS66i 6-Zone Amplifier integration."""

from __future__ import annotations

import logging
from typing import Any

from pyws66i import WS66i, get_ws66i
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_SOURCE_1,
    CONF_SOURCE_2,
    CONF_SOURCE_3,
    CONF_SOURCE_4,
    CONF_SOURCE_5,
    CONF_SOURCE_6,
    CONF_SOURCES,
    DOMAIN,
    INIT_OPTIONS_DEFAULT,
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

OPTIONS_SCHEMA = {vol.Optional(source): str for source in SOURCES}

DATA_SCHEMA = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})

FIRST_ZONE = 11


@callback
def _sources_from_config(data: dict[str, str]) -> dict[str, str]:
    sources_config = {
        str(idx + 1): data.get(source) for idx, source in enumerate(SOURCES)
    }

    return {
        index: name.strip()
        for index, name in sources_config.items()
        if (name is not None and name.strip() != "")
    }


def _verify_connection(ws66i: WS66i) -> bool:
    """Verify a connection can be made to the WS66i."""
    try:
        ws66i.open()
    except ConnectionError as err:
        raise CannotConnect from err

    # Connection successful. Verify correct port was opened
    # Test on FIRST_ZONE because this zone will always be valid
    ret_val = ws66i.zone_status(FIRST_ZONE)

    ws66i.close()

    return bool(ret_val)


async def validate_input(
    hass: HomeAssistant, input_data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    ws66i: WS66i = get_ws66i(input_data[CONF_IP_ADDRESS])

    is_valid: bool = await hass.async_add_executor_job(_verify_connection, ws66i)
    if not is_valid:
        raise CannotConnect("Not a valid WS66i connection")

    # Return info that you want to store in the config entry.
    return {CONF_IP_ADDRESS: input_data[CONF_IP_ADDRESS]}


class WS66iConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WS66i 6-Zone Amplifier."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Data is valid. Create a config entry.
                return self.async_create_entry(
                    title="WS66i Amp",
                    data=info,
                    options={CONF_SOURCES: INIT_OPTIONS_DEFAULT},
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> Ws66iOptionsFlowHandler:
        """Define the config flow to handle options."""
        return Ws66iOptionsFlowHandler()


@callback
def _key_for_source(
    index: int, source: str, previous_sources: dict[str, str]
) -> vol.Required:
    return vol.Required(
        source, description={"suggested_value": previous_sources[str(index)]}
    )


class Ws66iOptionsFlowHandler(OptionsFlow):
    """Handle a WS66i options flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="Source Names",
                data={CONF_SOURCES: _sources_from_config(user_input)},
            )

        # Fill form with previous source names
        previous_sources = self.config_entry.options[CONF_SOURCES]
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
