"""Config flow to configure the SimpliSafe component."""
from simplipy import API
from simplipy.errors import (
    InvalidCredentialsError,
    PendingAuthorizationError,
    SimplipyError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from . import async_get_client_id
from .const import DOMAIN, LOGGER  # pylint: disable=unused-import


class SimpliSafeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SimpliSafe config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.full_data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_CODE): str,
            }
        )
        self.password_data_schema = vol.Schema({vol.Required(CONF_PASSWORD): str})

        self._code = None
        self._password = None
        self._username = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return SimpliSafeOptionsFlowHandler(config_entry)

    async def _async_get_simplisafe_api(self):
        """Get an authenticated SimpliSafe API client."""
        client_id = await async_get_client_id(self.hass)
        websession = aiohttp_client.async_get_clientsession(self.hass)

        return await API.login_via_credentials(
            self._username,
            self._password,
            client_id=client_id,
            session=websession,
        )

    async def _async_login_during_step(self, *, step_id, form_schema):
        """Attempt to log into the API from within a config flow step."""
        errors = {}

        try:
            simplisafe = await self._async_get_simplisafe_api()
        except PendingAuthorizationError:
            LOGGER.info("Awaiting confirmation of MFA email click")
            return await self.async_step_mfa()
        except InvalidCredentialsError:
            errors = {"base": "invalid_credentials"}
        except SimplipyError as err:
            LOGGER.error("Unknown error while logging into SimpliSafe: %s", err)
            errors = {"base": "unknown"}

        if errors:
            return self.async_show_form(
                step_id=step_id,
                data_schema=form_schema,
                errors=errors,
            )

        return await self.async_step_finish(
            {
                CONF_USERNAME: self._username,
                CONF_TOKEN: simplisafe.refresh_token,
                CONF_CODE: self._code,
            }
        )

    async def async_step_finish(self, user_input=None):
        """Handle finish config entry setup."""
        existing_entry = await self.async_set_unique_id(self._username)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            return self.async_abort(reason="reauth_successful")
        return self.async_create_entry(title=self._username, data=user_input)

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_mfa(self, user_input=None):
        """Handle multi-factor auth confirmation."""
        if user_input is None:
            return self.async_show_form(step_id="mfa")

        try:
            simplisafe = await self._async_get_simplisafe_api()
        except PendingAuthorizationError:
            LOGGER.error("Still awaiting confirmation of MFA email click")
            return self.async_show_form(
                step_id="mfa", errors={"base": "still_awaiting_mfa"}
            )

        return await self.async_step_finish(
            {
                CONF_USERNAME: self._username,
                CONF_TOKEN: simplisafe.refresh_token,
                CONF_CODE: self._code,
            }
        )

    async def async_step_reauth(self, config):
        """Handle configuration by re-auth."""
        self._code = config.get(CONF_CODE)
        self._username = config[CONF_USERNAME]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=self.password_data_schema
            )

        self._password = user_input[CONF_PASSWORD]

        return await self._async_login_during_step(
            step_id="reauth_confirm", form_schema=self.password_data_schema
        )

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=self.full_data_schema
            )

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        self._code = user_input.get(CONF_CODE)
        self._password = user_input[CONF_PASSWORD]
        self._username = user_input[CONF_USERNAME]

        return await self._async_login_during_step(
            step_id="user", form_schema=self.full_data_schema
        )


class SimpliSafeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a SimpliSafe options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CODE,
                        default=self.config_entry.options.get(CONF_CODE),
                    ): str
                }
            ),
        )
