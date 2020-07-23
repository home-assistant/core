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
        self.data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_CODE): str,
            }
        )

        self._post_mfa_user_input = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return SimpliSafeOptionsFlowHandler(config_entry)

    async def _async_get_simplisafe_api(self, user_input):
        """Attempt to log into SimpliSafe."""
        client_id = await async_get_client_id(self.hass)
        websession = aiohttp_client.async_get_clientsession(self.hass)

        return await API.login_via_credentials(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            client_id=client_id,
            session=websession,
        )

    async def async_step_mfa(self, user_input=None):
        """Handle the start of the config flow."""
        if user_input is None:
            return self.async_show_form(step_id="mfa")

        try:
            simplisafe = await self._async_get_simplisafe_api(self._post_mfa_user_input)
        except SimplipyError as err:
            LOGGER.error("Unknown error while logging into SimpliSafe: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
                errors={"base": "unknown"},
            )

        return self.async_create_entry(
            title=self._post_mfa_user_input[CONF_USERNAME],
            data={
                CONF_USERNAME: self._post_mfa_user_input[CONF_USERNAME],
                CONF_TOKEN: simplisafe.refresh_token,
                CONF_CODE: self._post_mfa_user_input.get(CONF_CODE),
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=self.data_schema)

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        try:
            simplisafe = await self._async_get_simplisafe_api(user_input)
        except PendingAuthorizationError:
            LOGGER.info("Awaiting confirmation of MFA email click")
            self._post_mfa_user_input = user_input
            return self.async_show_form(step_id="mfa")
        except InvalidCredentialsError:
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
                errors={"base": "invalid_credentials"},
            )
        except SimplipyError as err:
            LOGGER.error("Unknown error while logging into SimpliSafe: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
                errors={"base": "unknown"},
            )

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_TOKEN: simplisafe.refresh_token,
                CONF_CODE: user_input.get(CONF_CODE),
            },
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
                        CONF_CODE, default=self.config_entry.options.get(CONF_CODE),
                    ): str
                }
            ),
        )
