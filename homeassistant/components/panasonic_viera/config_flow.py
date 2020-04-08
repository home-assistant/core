"""Config flow for Panasonic Viera TV integration."""
import logging

from panasonic_viera import RemoteControl, SOAPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PIN,
    CONF_PORT,
)
from homeassistant.core import callback

from .const import (
    CONF_APP_ID,
    CONF_APP_POWER,
    CONF_ENCRYPTION_KEY,
    DEFAULT_APP_POWER,
    DEFAULT_BROADCAST_ADDRESS,
    DEFAULT_MAC,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_NOT_CONNECTED,
    RESULT_INVALID_PIN_CODE,
    RESULT_NOT_CONNECTED,
    TV_TYPE_ENCRYPTED,
    TV_TYPE_NONENCRYPTED,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Panasonic Viera."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    _remote = None

    _data = {
        CONF_HOST: None,
        CONF_MAC: None,
        CONF_BROADCAST_ADDRESS: None,
        CONF_NAME: None,
        CONF_PORT: None,
        CONF_APP_POWER: None,
    }

    async def async_step_user(self, user_input):
        """Handle the initial step."""
        if user_input:
            await self.async_load_data(user_input)
            return await self.async_create_remote()

        return self._show_user_form()

    async def async_step_pairing(self, user_input=None):
        """Handle the pairing step."""
        if user_input:
            return await self.async_handle_pairing(user_input[CONF_PIN])

        return self._show_pair_form()

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        await self.async_load_data(import_config)
        return await self.async_create_remote()

    @callback
    def _show_user_form(self, errors=None):
        """Show the initial form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): str,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Optional(CONF_MAC, default=DEFAULT_MAC): str,
                    vol.Optional(
                        CONF_BROADCAST_ADDRESS, default=DEFAULT_BROADCAST_ADDRESS
                    ): str,
                    vol.Optional(CONF_APP_POWER, default=DEFAULT_APP_POWER): bool,
                }
            ),
            errors=errors,
        )

    @callback
    def _show_pair_form(self, errors=None):
        """Show the pairing form to the user."""
        self._remote.request_pin_code()
        return self.async_show_form(
            step_id="pairing", data_schema=vol.Schema({vol.Required(CONF_PIN): str,}),
        )

    async def async_load_data(self, config):
        """Load the data."""
        self._data[CONF_HOST] = config[CONF_HOST]
        self._data[CONF_MAC] = config[CONF_MAC]
        self._data[CONF_BROADCAST_ADDRESS] = config[CONF_BROADCAST_ADDRESS]
        self._data[CONF_NAME] = config[CONF_NAME]
        self._data[CONF_PORT] = config[CONF_PORT]
        self._data[CONF_APP_POWER] = config[CONF_APP_POWER]

        await self.async_set_unique_id(
            self._data[CONF_MAC] if self._data[CONF_MAC] else self._data[CONF_HOST]
        )

    async def async_create_remote(self):
        """Create the remote."""
        try:
            self._remote = RemoteControl(self._data[CONF_HOST], self._data[CONF_PORT])

            if self._remote._type == TV_TYPE_ENCRYPTED:
                return await self.async_step_pairing()
            elif self._remote._type == TV_TYPE_NONENCRYPTED:
                return self.async_create_entry(
                    title=self._data[CONF_NAME], data=self._data,
                )
        except Exception as err:
            _LOGGER.error(repr(err))
            return self._show_user_form({"base": ERROR_NOT_CONNECTED})

    async def async_handle_pairing(self, pin):
        """Handle pairing."""
        try:
            self._remote.authorize_pin_code(pincode=pin)
        except SOAPError as err:
            _LOGGER.error(repr(err))
            return self.async_abort(reason=RESULT_INVALID_PIN_CODE)
        except Exception as err:
            _LOGGER.error(repr(err))
            return self.async_abort(reason=RESULT_NOT_CONNECTED)

        enc_data = {
            CONF_APP_ID: self._remote._app_id,
            CONF_ENCRYPTION_KEY: self._remote._enc_key,
        }

        self._data = {**self._data, **enc_data}

        return self.async_create_entry(title=self._data[CONF_NAME], data=self._data,)
