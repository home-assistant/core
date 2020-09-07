"""Config flow for Goal Zero Yeti integration."""
import logging

from goalzero import GoalZero, exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"host": str, "name": str})


class GoalZeroFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goal Zero Yeti."""

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
            host = user_input[CONF_HOST] if is_import else f"{user_input[CONF_HOST]}"
            name = user_input[CONF_NAME]
            endpoint = f"{host}"

            if await self._async_endpoint_existed(endpoint):
                return self.async_abort(reason="already_configured")

            try:
                await self._async_try_connect(host)
                return self.async_create_entry(
                    title=name, data={CONF_HOST: host, CONF_NAME: name},
                )
            except exceptions.ConnectError:
                errors["base"] = "connect_timeout"
                _LOGGER.exception("No route to device at %s", host)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST) or ""
                    ): str,
                    vol.Optional(
                        CONF_NAME, default=user_input.get(CONF_NAME) or DEFAULT_NAME
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_endpoint_existed(self, endpoint):
        existing_endpoints = [
            f"{entry.data.get(CONF_HOST)}" for entry in self._async_current_entries()
        ]
        return endpoint in existing_endpoints

    async def _async_try_connect(self, host):
        session = async_get_clientsession(self.hass)
        api = GoalZero(host, self.hass.loop, session)
        try:
            await api.get_state()
        except exceptions.ConnectError:
            return False
