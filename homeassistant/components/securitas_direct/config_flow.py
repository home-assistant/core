"""Config flow for securitas direct integration."""

from pysecuritas.core.session import ConnectionException, Session
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_COUNTRY,
    CONF_INSTALLATION,
    CONF_LANG,
    DOMAIN,
    MULTI_SEC_CONFIGS,
    RELOADED,
    STEP_REAUTH,
    STEP_USER,
    UNABLE_TO_CONNECT,
)


def _connect(session):
    """Connects to securitas."""

    session.connect()

    return True


class SecuritasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for securitas direct."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize config flow."""

        self.config_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_INSTALLATION): str,
                vol.Optional(CONF_COUNTRY, default="ES"): str,
                vol.Optional(CONF_LANG, default="es"): str,
                vol.Optional(CONF_CODE, default=None): int,
            }
        )

    async def connect(self, step_id, config):
        """Handles securitas direct login."""

        uid = config[CONF_INSTALLATION]
        try:
            session = Session(
                config[CONF_USERNAME],
                config[CONF_PASSWORD],
                uid,
                config[CONF_COUNTRY],
                config[CONF_LANG],
            )
            await self.hass.async_add_executor_job(_connect, session)
        except (ConnectionException, ConnectTimeout, HTTPError):
            return self.async_show_form(
                step_id=step_id,
                data_schema=self.config_schema,
                errors={"base": UNABLE_TO_CONNECT},
            )

        return await self.create_entry(config, uid)

    async def show_form_or_connect(self, step, user_input):
        """
        Shows a form asking for configuration or connects to securitas
        if inputs are already provided
        """

        if user_input is None:
            return self.async_show_form(step_id=step, data_schema=self.config_schema)

        return await self.connect(step, user_input)

    async def create_entry(self, config_data, uid):
        """Creates an entry."""

        existing_entry = await self.async_set_unique_id(uid)
        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=config_data
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason=RELOADED)

        return self.async_create_entry(title=uid, data=config_data)

    async def async_step_user(self, user_input=None):
        """Initial user setup."""
        if self._async_current_entries():
            return self.async_abort(reason=MULTI_SEC_CONFIGS)

        return await self.show_form_or_connect(STEP_USER, user_input)

    async def async_step_import(self, import_config):
        """Imports a config from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_reauth(self, config):
        """Reauthenticate."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Confirm reauthenticate."""

        return await self.show_form_or_connect(STEP_REAUTH, user_input)
