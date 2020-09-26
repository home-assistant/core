"""Config flow to configure the Pi-hole integration."""
import logging

from hole import Hole
from hole.exceptions import HoleError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.pi_hole.const import (  # pylint: disable=unused-import
    CONF_LOCATION,
    DEFAULT_LOCATION,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class PiHoleFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Pi-hole config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self.async_step_init(user_input)

    async def async_step_import(self, user_input=None):
        """Handle a flow initiated by import."""
        return await self.async_step_init(user_input, is_import=True)

    async def async_step_init(self, user_input, is_import=False):
        """Handle init step of a flow."""
        errors = {}

        if user_input is not None:
            host = (
                user_input[CONF_HOST]
                if is_import
                else f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            name = user_input[CONF_NAME]
            location = user_input[CONF_LOCATION]
            tls = user_input[CONF_SSL]
            verify_tls = user_input[CONF_VERIFY_SSL]
            api_token = user_input.get(CONF_API_KEY)
            endpoint = f"{host}/{location}"

            if await self._async_endpoint_existed(endpoint):
                return self.async_abort(reason="already_configured")

            try:
                await self._async_try_connect(
                    host, location, tls, verify_tls, api_token
                )
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_NAME: name,
                        CONF_LOCATION: location,
                        CONF_SSL: tls,
                        CONF_VERIFY_SSL: verify_tls,
                        CONF_API_KEY: api_token,
                    },
                )
            except HoleError as ex:
                _LOGGER.debug("Connection failed: %s", ex)
                if is_import:
                    _LOGGER.error("Failed to import: %s", ex)
                    return self.async_abort(reason="cannot_connect")
                errors["base"] = "cannot_connect"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST) or ""
                    ): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT) or 80
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME) or DEFAULT_NAME
                    ): str,
                    vol.Required(
                        CONF_LOCATION,
                        default=user_input.get(CONF_LOCATION) or DEFAULT_LOCATION,
                    ): str,
                    vol.Optional(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY) or ""
                    ): str,
                    vol.Required(
                        CONF_SSL, default=user_input.get(CONF_SSL) or DEFAULT_SSL
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL) or DEFAULT_VERIFY_SSL,
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def _async_endpoint_existed(self, endpoint):
        existing_endpoints = [
            f"{entry.data.get(CONF_HOST)}/{entry.data.get(CONF_LOCATION)}"
            for entry in self._async_current_entries()
        ]
        return endpoint in existing_endpoints

    async def _async_try_connect(self, host, location, tls, verify_tls, api_token):
        session = async_get_clientsession(self.hass, verify_tls)
        pi_hole = Hole(
            host,
            self.hass.loop,
            session,
            location=location,
            tls=tls,
            api_token=api_token,
        )
        await pi_hole.get_data()
