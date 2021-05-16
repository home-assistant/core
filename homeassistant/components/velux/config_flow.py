"""Config flow for velux integration."""
import logging

from pyvlx import PyVLX, PyVLXException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_PASSWORD): str}
)


class VeluxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for velux."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                host = user_input[CONF_HOST]
                password = user_input[CONF_PASSWORD]

                pyvlx = PyVLX(host=host, password=password)
                await pyvlx.connect()

                await pyvlx.disconnect()

                return self.async_create_entry(
                    title=host,
                    data=user_input,
                )
            except PyVLXException as ex:
                _LOGGER.exception("Unable to connect to Velux gateway: %s", ex)
                errors["base"] = "invalid_auth"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unable to connect to Velux gateway: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import config from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_config[CONF_HOST]})

        return await self.async_step_user(import_config)
