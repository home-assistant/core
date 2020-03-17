"""Config flow for Logitech Harmony Hub integration."""
import logging
from urllib.parse import urlparse

import aioharmony.exceptions as harmony_exceptions
from aioharmony.harmonyapi import HarmonyAPI
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components import ssdp
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    DEFAULT_DELAY_SECS,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str}, extra=vol.ALLOW_EXTRA
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    harmony = HarmonyAPI(ip_address=data[CONF_HOST])

    _LOGGER.debug("harmony:%s", harmony)

    try:
        if not await harmony.connect():
            await harmony.close()
            raise CannotConnect
    except harmony_exceptions.TimeOut:
        raise CannotConnect

    # As a last resort we get the name from the harmony client
    # in the event a name was not provided
    if CONF_NAME not in data or data[CONF_NAME] is None or data[CONF_NAME] == "":
        data[CONF_NAME] = harmony.name

    return {CONF_NAME: data[CONF_NAME], CONF_HOST: data[CONF_HOST]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Logitech Harmony Hub."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Harmony config flow."""
        self.harmony_config = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
                config_entry = self.async_create_entry(title=info[CONF_NAME], data=info)
                # Options from yaml are preserved
                options = _options_from_user_input(user_input)
                if options:
                    config_entry["options"] = options
                return config_entry
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Return form
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Harmony device."""
        parsed_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])
        friendly_name = discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME]

        # The unique id is explicitly not set here because
        # entities can be imported from yaml by name via
        # discovery.  If the unique id is set here, it will
        # start the config flow and block the import which will
        # break users config on upgrade.

        # pylint: disable=no-member
        self.context["title_placeholders"] = {"name": friendly_name}

        self.harmony_config = {
            CONF_HOST: parsed_url.hostname,
            CONF_NAME: friendly_name,
        }

        return await self.async_step_link()

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Harmony."""
        errors = {}

        if user_input is not None:
            # Wait until they say they want to link to set the unique
            # id in case its about to be imported by the platform.
            await self.async_set_unique_id(self.harmony_config[CONF_HOST])
            # Abort if already setup
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, self.harmony_config)
                return self.async_create_entry(title=info[CONF_NAME], data=info)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="link",
            errors=errors,
            description_placeholders={
                "name": self.harmony_config[CONF_NAME],
                "host": self.harmony_config[CONF_HOST],
            },
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


def _options_from_user_input(user_input):
    options = {}
    if ATTR_ACTIVITY in user_input:
        options[ATTR_ACTIVITY] = user_input[ATTR_ACTIVITY]
    if ATTR_DELAY_SECS in user_input:
        options[ATTR_DELAY_SECS] = user_input[ATTR_DELAY_SECS]
    return options


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Harmony."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        remote = self.hass.data[DOMAIN][self.config_entry.entry_id]

        data_schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_DELAY_SECS,
                    default=self.config_entry.options.get(
                        ATTR_DELAY_SECS, DEFAULT_DELAY_SECS
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    ATTR_ACTIVITY, default=self.config_entry.options.get(ATTR_ACTIVITY),
                ): vol.In(remote.activity_names),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
