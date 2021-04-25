"""Config flow for Goal Zero Yeti integration."""
import logging

from goalzero import Yeti, exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"host": str, "name": str})


class GoalZeroFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goal Zero Yeti."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            if await self._async_endpoint_existed(host):
                return self.async_abort(reason="already_configured")

            try:
                await self._async_try_connect(host)
            except exceptions.ConnectError:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Error connecting to device at %s", host)
            except exceptions.InvalidHost:
                errors["base"] = "invalid_host"
                _LOGGER.error("Invalid host at %s", host)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_NAME: name},
                )

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
        for entry in self._async_current_entries():
            if endpoint == entry.data.get(CONF_HOST):
                return True
        return False

    async def _async_try_connect(self, host):
        session = async_get_clientsession(self.hass)
        api = Yeti(host, self.hass.loop, session)
        await api.get_state()
