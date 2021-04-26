"""Config flow for brunt integration."""
import logging

from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ServerDisconnectedError
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

    def __init__(self):
        """Start the Brunt config flow."""
        self._reauth_entry = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = None
        bapi = BruntClientAsync(
            username=user_input[CONF_USERNAME], password=user_input[CONF_PASSWORD]
        )
        try:
            await bapi.async_login()
        except ClientResponseError as exc:
            if exc.status == 403:
                _LOGGER.warning("Brunt Credentials are incorrect")
                errors = {"base": "invalid_auth"}
            else:
                _LOGGER.warning("Unknown error when connecting to Brunt: %s", exc)
                errors = {"base": "unknown"}
        except ServerDisconnectedError:
            _LOGGER.warning("Cannot connect to Brunt")
            errors = {"base": "cannot_connect"}
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.warning("Unknown error when connecting to Brunt: %s", exc)
            errors = {"base": "unknown"}
        finally:
            await bapi.async_close()
        if errors is not None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        if self._reauth_entry is None or self._reauth_entry.unique_id != self.unique_id:
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_USERNAME],
                data=user_input,
            )

        self.hass.config_entries.async_update_entry(self._reauth_entry, data=user_input)
        await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)

        return self.async_abort(reason="reauth_successful")

    async def async_step_import(self, import_config):
        """Import config from configuration.yaml."""
        entries = self._async_current_entries()
        for entry in entries:
            if entry.data[CONF_USERNAME] == import_config[CONF_USERNAME]:
                return self.async_abort(reason="already_configured")

        return await self.async_step_user(import_config)

    async def async_step_reauth(self, user_input=None):
        """Perform reauth if the user credentials have changed."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()
