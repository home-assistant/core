"""Config flow for Panasonic Viera TV integration."""
from functools import partial
import logging
from urllib.request import URLError

from panasonic_viera import TV_TYPE_ENCRYPTED, RemoteControl, SOAPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_PORT
from homeassistant.core import callback

from .const import (  # pylint: disable=unused-import
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_ON_ACTION,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_INVALID_PIN_CODE,
    ERROR_NOT_CONNECTED,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Panasonic Viera."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Panasonic Viera config flow."""
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
            except (TimeoutError, URLError, OSError) as err:
                _LOGGER.error("Could not establish remote connection: %s", err)
                self._errors = {"base": ERROR_NOT_CONNECTED}
                return await self.async_step_user()
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unknown error: %s", err)
                self._errors = {"base": ERROR_UNKNOWN}
                return await self.async_step_user()

            encryption_data = {
                CONF_APP_ID: self._remote.app_id,
                CONF_ENCRYPTION_KEY: self._remote.enc_key,
            }

            self._data = {**self._data, **encryption_data}

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
        except (TimeoutError, URLError, OSError) as err:
            _LOGGER.error("Could not establish remote connection: %s", err)
            self._errors = {"base": ERROR_NOT_CONNECTED}
            return await self.async_step_user()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("An unknown error occurred: %s", err)
            self._errors = {"base": ERROR_UNKNOWN}
            return await self.async_step_user()

        if self._remote.type == TV_TYPE_ENCRYPTED:
            return await self.async_step_pairing()

        return self.async_create_entry(title=self._data[CONF_NAME], data=self._data,)

    @callback
    def _show_user_form(self):
        """Show the initial form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=self._data[CONF_HOST]
                        if self._data[CONF_HOST] is not None
                        else "",
                    ): str,
                    vol.Optional(
                        CONF_NAME,
                        default=self._data[CONF_NAME]
                        if self._data[CONF_NAME] is not None
                        else DEFAULT_NAME,
                    ): str,
                }
            ),
            errors=self._errors,
        )

    @callback
    def _show_pair_form(self):
        """Show the pairing form to the user."""
        if self._errors is not None and self._errors["base"] in [
            ERROR_NOT_CONNECTED,
            ERROR_UNKNOWN,
        ]:
            self._errors = None

        self._remote.request_pin_code(name="Home Assistant")
        return self.async_show_form(
            step_id="pairing",
            data_schema=vol.Schema({vol.Required(CONF_PIN): str}),
            errors=self._errors,
            description_placeholders={"name": self._data[CONF_NAME]},
        )
