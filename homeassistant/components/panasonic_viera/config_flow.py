"""Config flow for Panasonic Viera TV integration."""
import logging

from panasonic_viera import (
    RemoteControl,
    SOAPError,
    TV_TYPE_ENCRYPTED,
    TV_TYPE_NONENCRYPTED,
)

import voluptuous as vol

from functools import partial

from urllib.request import URLError

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_PORT,
)
from homeassistant.core import callback

from .const import (
    CONF_ON_ACTION,
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_NOT_CONNECTED,
    ERROR_INVALID_PIN_CODE,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Panasonic Viera."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self._data = {
            CONF_HOST: None,
            CONF_NAME: None,
            CONF_PORT: None,
            CONF_ON_ACTION: None,
        }

        self._remote = None

        self._errors = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            await self.async_load_data(user_input)
            return await self.async_create_remote()

        return self._show_user_form()

    async def async_step_pairing(self, user_input=None):
        """Handle the pairing step."""
        if user_input is not None:
            pin = user_input[CONF_PIN]
            try:
                self._remote.authorize_pin_code(pincode=pin)
            except SOAPError as err:
                _LOGGER.error("Invalid PIN code: %s", err)
                self._errors = {"base": ERROR_INVALID_PIN_CODE}
                return await self.async_step_user(self._data)
            except (URLError, TimeoutError) as err:
                _LOGGER.error("Could not establish remote connection: %s", err)
                self._errors = {"base": ERROR_NOT_CONNECTED}
                return await self.async_step_user()
            except Exception as err:
                _LOGGER.error("Unknown error: %s", err)
                self._errors = {"base": ERROR_UNKNOWN}
                return await self.async_step_user()

            enc_data = {
                CONF_APP_ID: self._remote._app_id,
                CONF_ENCRYPTION_KEY: self._remote._enc_key,
            }

            self._data = {**self._data, **enc_data}

            return self.async_create_entry(
                title=self._data[CONF_NAME], data=self._data,
            )

        return self._show_pair_form()

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        await self.async_load_data(import_config)
        return await self.async_create_remote()

    async def async_load_data(self, config):
        """Load the data."""
        self._data = config

        self._data[CONF_PORT] = (
            self._data[CONF_PORT] if CONF_PORT in self._data else DEFAULT_PORT
        )
        self._data[CONF_ON_ACTION] = (
            self._data[CONF_ON_ACTION] if CONF_ON_ACTION in self._data else None
        )

        await self.async_set_unique_id(self._data[CONF_HOST])
        self._abort_if_unique_id_configured()

    async def async_create_remote(self):
        """Create the remote."""
        try:
            self._remote = await self.hass.async_add_executor_job(
                partial(RemoteControl, self._data[CONF_HOST], self._data[CONF_PORT])
            )
        except (URLError, TimeoutError) as err:
            _LOGGER.error("Could not establish remote connection: %s", err)
            self._errors = {"base": ERROR_NOT_CONNECTED}
            return await self.async_step_user()
        except Exception as err:
            _LOGGER.error("Unknown error: %s", err)
            self._errors = {"base": ERROR_UNKNOWN}
            return await self.async_step_user()

        if self._remote._type == TV_TYPE_ENCRYPTED:
            return await self.async_step_pairing()
        elif self._remote._type == TV_TYPE_NONENCRYPTED:
            return self.async_create_entry(
                title=self._data[CONF_NAME], data=self._data,
            )

    @callback
    def _show_user_form(self, errors=None):
        """Show the initial form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=self._errors,
        )

    @callback
    def _show_pair_form(self, errors=None):
        """Show the pairing form to the user."""
        self._remote.request_pin_code()
        return self.async_show_form(
            step_id="pairing",
            data_schema=vol.Schema({vol.Required(CONF_PIN): str,}),
            errors=self._errors,
            description_placeholders={"tv_name": self._data[CONF_NAME],},
        )
