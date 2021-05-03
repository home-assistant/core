"""Config flow for Awair."""
from __future__ import annotations

from python_awair import Awair
from python_awair.exceptions import AuthError, AwairError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER


class AwairFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Awair."""

    VERSION = 1

    async def async_step_import(self, conf: dict):
        """Import a configuration from config.yaml."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        user, error = await self._check_connection(conf[CONF_ACCESS_TOKEN])
        if error is not None:
            return self.async_abort(reason=error)

        await self.async_set_unique_id(user.email)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{user.email} ({user.user_id})",
            data={CONF_ACCESS_TOKEN: conf[CONF_ACCESS_TOKEN]},
        )

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            user, error = await self._check_connection(user_input[CONF_ACCESS_TOKEN])

            if user is not None:
                await self.async_set_unique_id(user.email)
                self._abort_if_unique_id_configured()

                title = f"{user.email} ({user.user_id})"
                return self.async_create_entry(title=title, data=user_input)

            if error != "invalid_access_token":
                return self.async_abort(reason=error)

            errors = {CONF_ACCESS_TOKEN: "invalid_access_token"}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )

    async def async_step_reauth(self, user_input: dict | None = None):
        """Handle re-auth if token invalid."""
        errors = {}

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN]
            _, error = await self._check_connection(access_token)

            if error is None:
                entry = await self.async_set_unique_id(self.unique_id)
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                return self.async_abort(reason="reauth_successful")

            if error != "invalid_access_token":
                return self.async_abort(reason=error)

            errors = {CONF_ACCESS_TOKEN: error}

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )

    async def _check_connection(self, access_token: str):
        """Check the access token is valid."""
        session = async_get_clientsession(self.hass)
        awair = Awair(access_token=access_token, session=session)

        try:
            user = await awair.user()
            devices = await user.devices()
            if not devices:
                return (None, "no_devices_found")

            return (user, None)

        except AuthError:
            return (None, "invalid_access_token")
        except AwairError as err:
            LOGGER.error("Unexpected API error: %s", err)
            return (None, "unknown")
