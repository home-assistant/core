"""Config flow for ecowitt."""
import asyncio
import logging

from pyecowitt import EcoWittListener
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_PORT,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_UNIT_BARO,
    CONF_UNIT_LIGHTNING,
    CONF_UNIT_RAIN,
    CONF_UNIT_WIND,
    CONF_UNIT_WINDCHILL,
    DATA_MODEL,
    DATA_PASSKEY,
    DOMAIN,
    UNIT_OPTS,
    W_TYPE_HYBRID,
    WIND_OPTS,
    WINDCHILL_OPTS,
)
from .schemas import DATA_SCHEMA

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect."""
    ecowitt = EcoWittListener(port=data[CONF_PORT])
    asyncio.create_task(ecowitt.listen())
    try:
        await asyncio.wait_for(ecowitt.wait_for_valid_data(), timeout=90.0)
    except asyncio.TimeoutError as error:
        raise CannotConnect from error
    passkey = ecowitt.get_sensor_value_by_key(DATA_PASSKEY)
    model = ecowitt.get_sensor_value_by_key(DATA_MODEL)
    await ecowitt.stop()
    return {"title": model, "passkey": passkey}


class EcowittConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the Ecowitt."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Give initial instructions for setup."""
        if user_input is not None:
            return await self.async_step_initial_options()

        return self.async_show_form(step_id="user")

    async def async_step_initial_options(self, user_input=None):
        """Ask the user for the setup options."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_PORT: user_input[CONF_PORT]})
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["passkey"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{info['title']} on port {user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="initial_options", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Call the options flow handler."""
        return EcowittOptionsFlowHandler(config_entry)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class EcowittOptionsFlowHandler(config_entries.OptionsFlow):
    """Ecowitt config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HASS options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UNIT_BARO,
                    default=self.config_entry.options.get(
                        CONF_UNIT_BARO,
                        CONF_UNIT_SYSTEM_METRIC,
                    ),
                ): vol.In(UNIT_OPTS),
                vol.Optional(
                    CONF_UNIT_WIND,
                    default=self.config_entry.options.get(
                        CONF_UNIT_WIND,
                        CONF_UNIT_SYSTEM_IMPERIAL,
                    ),
                ): vol.In(WIND_OPTS),
                vol.Optional(
                    CONF_UNIT_RAIN,
                    default=self.config_entry.options.get(
                        CONF_UNIT_RAIN,
                        CONF_UNIT_SYSTEM_IMPERIAL,
                    ),
                ): vol.In(UNIT_OPTS),
                vol.Optional(
                    CONF_UNIT_LIGHTNING,
                    default=self.config_entry.options.get(
                        CONF_UNIT_LIGHTNING,
                        CONF_UNIT_SYSTEM_IMPERIAL,
                    ),
                ): vol.In(UNIT_OPTS),
                vol.Optional(
                    CONF_UNIT_WINDCHILL,
                    default=self.config_entry.options.get(
                        CONF_UNIT_WINDCHILL,
                        W_TYPE_HYBRID,
                    ),
                ): vol.In(WINDCHILL_OPTS),
            }
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)
