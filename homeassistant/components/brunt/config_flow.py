"""Config flow for brunt integration."""
import logging

from aiohttp import ClientResponseError
from aiohttp.web import HTTPError
from brunt import BruntClientAsync
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class BruntConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for youless."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        bapi = BruntClientAsync(
            username=user_input[CONF_USERNAME], password=user_input[CONF_PASSWORD]
        )
        try:
            await bapi.async_login()
        except (HTTPError, ClientResponseError):
            _LOGGER.warning("Cannot connect to Brunt.")
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except Exception as exc:
            _LOGGER.warning("Unknown error when connecting to Brunt: %s", exc)
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": "unknown"},
            )
        finally:
            await bapi.async_close()
        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data=user_input,
        )

    async def async_step_import(self, import_config):
        """Import config from configuration.yaml."""
        entries = self._async_current_entries()
        for entry in entries:
            if entry.data[CONF_USERNAME] == import_config[CONF_USERNAME]:
                return self.async_abort(reason="already_configured")

        return await self.async_step_user(import_config)
