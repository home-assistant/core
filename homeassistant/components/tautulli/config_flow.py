"""Config flow for Tautulli."""
from __future__ import annotations

import logging
from typing import Any

from pytautulli import PyTautulli, PyTautulliHostConfiguration, exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEFAULT_NAME,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class TautulliConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tautulli."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            info, error = await self.validate_input(user_input)
            if error is None:
                await self.async_set_unique_id(info.pms_identifier)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )
            errors["base"] = error

        user_input = user_input or {}
        data_schema = {
            vol.Required(CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")): str,
            vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): str,
            vol.Optional(CONF_SSL, default=user_input.get(CONF_SSL, False)): bool,
            vol.Optional(
                CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)
            ): bool,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors or {},
        )

    async def async_step_reauth(self, config: dict[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None and entry:
            _input = dict(entry.data)
            _input[CONF_API_KEY] = user_input[CONF_API_KEY]
            _, error = await self.validate_input(dict(_input))
            if error is None:
                self.hass.config_entries.async_update_entry(entry, data=_input)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error
        user_input = user_input or {}
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                    ): str
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_KEY] == config[CONF_API_KEY]:
                _part = config[CONF_API_KEY][0:4]
                _msg = f"Tautulli yaml config with partial key {_part} has been imported. Please remove it"
                _LOGGER.warning(_msg)
                return self.async_abort(reason="already_configured")
        host_configuration = PyTautulliHostConfiguration(
            config[CONF_API_KEY],
            ipaddress=config[CONF_HOST],
            port=config.get(CONF_PORT, DEFAULT_PORT),
            ssl=config.get(CONF_SSL, DEFAULT_SSL),
            verify_ssl=config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            base_api_path=config.get(CONF_PATH, DEFAULT_PATH),
        )
        conf = {}
        conf[CONF_API_KEY] = host_configuration.api_token
        conf[CONF_URL] = host_configuration.base_url
        conf[CONF_SSL] = host_configuration.ssl
        conf[CONF_VERIFY_SSL] = host_configuration.verify_ssl
        return await self.async_step_user(conf)

    async def validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[Any, str | None]:
        """Try connecting to Tautulli."""
        try:
            api_client = PyTautulli(
                api_token=user_input[CONF_API_KEY],
                url=user_input[CONF_URL],
                session=async_get_clientsession(
                    self.hass, user_input.get(CONF_VERIFY_SSL, True)
                ),
                verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
                ssl=user_input[CONF_SSL],
            )
            return await api_client.async_get_server_info(), None
        except exceptions.PyTautulliConnectionException:
            return None, "cannot_connect"
        except exceptions.PyTautulliAuthenticationException:
            return None, "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            return None, "unknown"
