"""Config flow for Awair."""

from typing import Union

from python_awair import Awair
from python_awair.exceptions import AuthError, AwairError
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER  # pylint: disable=unused-import


class AwairFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Awair."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    async def async_step_import(self, conf: dict):
        """Import a configuration from config.yaml."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        await self._abort_if_configured(conf[CONF_ACCESS_TOKEN])

        user, errors = await self._check_access_token(conf[CONF_ACCESS_TOKEN])
        if errors is not None:
            return self.async_abort(reason="auth")

        return self.async_create_entry(
            title=f"{user.email} ({user.user_id})",
            data={CONF_ACCESS_TOKEN: conf[CONF_ACCESS_TOKEN]},
        )

    async def async_step_user(self, user_input: Union[dict, None] = None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            user, errors = await self._check_access_token(user_input[CONF_ACCESS_TOKEN])

            if not errors:
                await self._abort_if_configured(user_input[CONF_ACCESS_TOKEN])
                title = f"{user.email} ({user.user_id})"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )

    async def async_step_reauth(self, user_input: Union[dict, None] = None):
        """Handle re-auth if token invalid."""
        errors = {}

        if user_input is not None:
            if "config_entry" in user_input:
                if self.unique_id is None:
                    await self.async_set_unique_id(user_input["config_entry"].unique_id)
            elif CONF_ACCESS_TOKEN in user_input:
                access_token = user_input[CONF_ACCESS_TOKEN]
                user, errors = await self._check_access_token(access_token)
                if not errors:
                    return self.async_create_entry(
                        title=f"{user.email} ({user.user_id})",
                        data={CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN]},
                    )

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )

    async def _check_access_token(self, access_token: str):
        """Check the access token is valid."""
        session = async_get_clientsession(self.hass)
        awair = Awair(access_token=access_token, session=session)

        try:
            user = await awair.user()
            devices = await user.devices()
            if not devices:
                return self.async_abort(reason="no_devices")

            return (user, None)

        except AuthError:
            return (None, {CONF_ACCESS_TOKEN: "auth"})
        except AwairError as err:
            LOGGER.error("Unexpected API error: %s", err)
            return (None, {"base": "unknown"})

    async def _abort_if_configured(self, access_token: str):
        """Abort if this access_token has been set up."""
        await self.async_set_unique_id(access_token)
        self._abort_if_unique_id_configured()
