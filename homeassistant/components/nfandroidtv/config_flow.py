"""Config flow for NFAndroidTV integration."""
from __future__ import annotations

from asyncio.exceptions import TimeoutError
import logging

from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout
from httpcore import ConnectError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NFAndroidTVFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NFAndroidTV."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            error = await self._async_try_connect(host)
            if error is None:
                await self.async_set_unique_id(f"{host}_{DOMAIN}")
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=user_input[CONF_NAME] or host,
                    data={CONF_HOST: host, CONF_NAME: name},
                )
            errors["base"] = error

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

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == import_config[CONF_HOST]:
                _LOGGER.warning(
                    "Already configured. This yaml configuration has already been imported. Please remove it"
                )
                return self.async_abort(reason="already_configured")

        return await self.async_step_user(import_config)

    async def _async_try_connect(self, host):
        """Try connecting to Android TV / Fire TV."""
        try:
            session = async_get_clientsession(self.hass)
            async with timeout(DEFAULT_TIMEOUT, loop=self.hass.loop):
                await session.post(f"http://{host}:7676")
        except (ConnectError, TimeoutError, ClientConnectorError):
            _LOGGER.error("Error connecting to device at %s", host)
            return "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return
