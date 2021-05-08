"""Config flow for Logitech Harmony Hub integration."""
import logging
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import ssdp
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    DEFAULT_DELAY_SECS,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN, HARMONY_DATA, PREVIOUS_ACTIVE_ACTIVITY, UNIQUE_ID
from .util import (
    find_best_name_for_remote,
    find_unique_id_for_remote,
    get_harmony_client_if_available,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str}, extra=vol.ALLOW_EXTRA
)


async def validate_input(data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    harmony = await get_harmony_client_if_available(data[CONF_HOST])
    if not harmony:
        raise CannotConnect

    return {
        CONF_NAME: find_best_name_for_remote(data, harmony),
        CONF_HOST: data[CONF_HOST],
        UNIQUE_ID: find_unique_id_for_remote(harmony),
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Logitech Harmony Hub."""

    VERSION = 1

    def __init__(self):
        """Initialize the Harmony config flow."""
        self.harmony_config = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:

            try:
                validated = await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(validated[UNIQUE_ID])
                self._abort_if_unique_id_configured()
                return await self._async_create_entry_from_valid_input(
                    validated, user_input
                )

        # Return form
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Harmony device."""
        _LOGGER.debug("SSDP discovery_info: %s", discovery_info)

        parsed_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])
        friendly_name = discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME]

        if self._host_already_configured(parsed_url.hostname):
            return self.async_abort(reason="already_configured")

        self.context["title_placeholders"] = {"name": friendly_name}

        self.harmony_config = {
            CONF_HOST: parsed_url.hostname,
            CONF_NAME: friendly_name,
        }

        harmony = await get_harmony_client_if_available(parsed_url.hostname)

        if harmony:
            unique_id = find_unique_id_for_remote(harmony)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self.harmony_config[CONF_HOST]}
            )
            self.harmony_config[UNIQUE_ID] = unique_id

        return await self.async_step_link()

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Harmony."""
        errors = {}

        if user_input is not None:
            # Everything was validated in async_step_ssdp
            # all we do now is create.
            return await self._async_create_entry_from_valid_input(
                self.harmony_config, {}
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="link",
            errors=errors,
            description_placeholders={
                CONF_HOST: self.harmony_config[CONF_NAME],
                CONF_NAME: self.harmony_config[CONF_HOST],
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def _async_create_entry_from_valid_input(self, validated, user_input):
        """Single path to create the config entry from validated input."""

        data = {
            CONF_NAME: validated[CONF_NAME],
            CONF_HOST: validated[CONF_HOST],
        }
        # Options from yaml are preserved, we will pull them out when
        # we setup the config entry
        data.update(_options_from_user_input(user_input))

        return self.async_create_entry(title=validated[CONF_NAME], data=data)

    def _host_already_configured(self, host):
        """See if we already have a harmony entry matching the host."""
        for entry in self._async_current_entries():
            if CONF_HOST not in entry.data:
                continue

            if entry.data[CONF_HOST] == host:
                return True
        return False


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

        remote = self.hass.data[DOMAIN][self.config_entry.entry_id][HARMONY_DATA]

        data_schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_DELAY_SECS,
                    default=self.config_entry.options.get(
                        ATTR_DELAY_SECS, DEFAULT_DELAY_SECS
                    ),
                ): vol.Coerce(float),
                vol.Optional(
                    ATTR_ACTIVITY,
                    default=self.config_entry.options.get(
                        ATTR_ACTIVITY, PREVIOUS_ACTIVE_ACTIVITY
                    ),
                ): vol.In([PREVIOUS_ACTIVE_ACTIVITY, *remote.activity_names]),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
