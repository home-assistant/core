"""Config flow for Efesto."""
from collections import OrderedDict
import efestoclient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DEVICE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from .const import DOMAIN


@callback
def device_entries(hass):
    """Return the host,port tuples for the domain."""
    return set(
        entry.data[CONF_DEVICE] for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class EfestoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Efesto Config Flow handler."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def _entry_in_configuration_exists(self, user_input) -> bool:
        """Return True if device already exists in configuration."""
        device_id = user_input[CONF_DEVICE]
        if device_id in device_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """User initiated integration."""
        errors = {}
        if user_input is not None:
            # Validate user input
            url = user_input[CONF_URL]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            device_id = user_input[CONF_DEVICE]
            name = user_input.get(CONF_NAME, "Efesto")

            if self._entry_in_configuration_exists(user_input):
                return self.async_abort(reason="device_already_configured")

            try:
                client = efestoclient.EfestoClient(
                    url, username, password, device_id, False
                )
                client.get_status()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_URL: url,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_DEVICE: device_id,
                    },
                )
            except efestoclient.Error:
                errors["base"] = "efesto_error"
        else:
            user_input = {}

        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_URL, default=user_input.get(CONF_URL))] = str
        data_schema[
            vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME))
        ] = str
        data_schema[
            vol.Required(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD))
        ] = str
        data_schema[
            vol.Required(CONF_DEVICE, default=user_input.get(CONF_DEVICE))
        ] = str
        data_schema[vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME))] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        if self._entry_in_configuration_exists(user_input):
            return self.async_abort(reason="device_already_configured")
        return self.async_create_entry(
            title=user_input.get(CONF_NAME, "Efesto"),
            data={
                CONF_URL: user_input[CONF_URL],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_DEVICE: user_input[CONF_DEVICE],
            },
        )
