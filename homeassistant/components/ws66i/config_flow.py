"""Config flow for WS66i 6-Zone Amplifier integration."""
import logging

from pyws66i import WS66i, get_ws66i
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_IP_ADDRESS

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


@core.callback
def _sources_from_config(data):
    sources_config = {
        str(idx + 1): data.get(source) for idx, source in enumerate(SOURCES)
    }

    return {
        index: name.strip()
        for index, name in sources_config.items()
        if (name is not None and name.strip() != "")
    }


async def validate_input(hass: core.HomeAssistant, input_data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    ws66i: WS66i = get_ws66i(input_data[CONF_IP_ADDRESS])
    await hass.async_add_executor_job(ws66i.open)
    # No exception. run a simple test to make sure we opened correct port
    # Test on FIRST_ZONE because this zone will always be valid
    ret_val = await hass.async_add_executor_job(ws66i.zone_status, FIRST_ZONE)
    if ret_val is None:
        ws66i.close()
        raise ConnectionError("Not a valid WS66i connection")

    # Validation done. No issues. Close the connection
    ws66i.close()

    # Return info that you want to store in the config entry.
    return {CONF_IP_ADDRESS: input_data[CONF_IP_ADDRESS]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WS66i 6-Zone Amplifier."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                # Data is valid. Add default values for options flow.
                return self.async_create_entry(
                    title="WS66i Amp",
                    data=info,
                    options={CONF_SOURCES: INIT_OPTIONS_DEFAULT},
                )
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @core.callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return Ws66iOptionsFlowHandler(config_entry)


@core.callback
def _key_for_source(index, source, previous_sources):
    key = vol.Required(
        source, description={"suggested_value": previous_sources[str(index)]}
    )

    return key


class Ws66iOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a WS66i options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
