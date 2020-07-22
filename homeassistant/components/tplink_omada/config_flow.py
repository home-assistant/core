"""Support for TP-Link Omada."""
import logging

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_TIMEOUT, CONF_NAME,
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (  # pylint:disable=unused-import
    DOMAIN as OMADA_DOMAIN,
    CONF_DNSRESOLVE,
    CONF_SSLVERIFY,
    DEFAULT_SSLVERIFY,
    DEFAULT_DNSRESOLVE,
    DEFAULT_TIMEOUT,
)
from .common import login


_LOGGER = logging.getLogger(__name__)


class OmadaConfigFlow(config_entries.ConfigFlow, domain=OMADA_DOMAIN):
    """TP-Link Omada Controller Conflig flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input):
        """Handle init step of a flow."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            host = user_input[CONF_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            verify_tls = user_input[CONF_SSLVERIFY]
            timeout = user_input[CONF_TIMEOUT]
            dns_resolve = user_input[CONF_DNSRESOLVE]

            if await self._async_controller_existed(host):
                return self.async_abort(reason="already_configured")

            if not await self._async_try_connect(host, username, password, timeout, verify_tls):
                errors["base"] = "cannot_connect"

            if not errors:
                try:
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_NAME: name,
                            CONF_HOST: host,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_TIMEOUT: timeout,
                            CONF_SSLVERIFY: verify_tls,
                            CONF_DNSRESOLVE: dns_resolve,
                        },
                    )
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception as exp:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception: %s", exp)
                    errors["base"] = "cannot_connect"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME,
                             default=user_input.get(CONF_NAME) or ""
                             ): str,
                vol.Required(CONF_HOST,
                             default=user_input.get(CONF_HOST) or ""
                             ): str,
                vol.Required(CONF_USERNAME,
                             default=user_input.get(CONF_USERNAME) or ""
                             ): str,
                vol.Required(CONF_PASSWORD,
                             default=user_input.get(CONF_PASSWORD) or ""
                             ): str,
                vol.Optional(CONF_SSLVERIFY,
                             default=user_input.get(CONF_SSLVERIFY) or DEFAULT_SSLVERIFY
                             ): bool,
                vol.Optional(CONF_TIMEOUT,
                             default=user_input.get(CONF_TIMEOUT) or DEFAULT_TIMEOUT
                             ): int,
                vol.Optional(CONF_DNSRESOLVE,
                             default=user_input.get(CONF_DNSRESOLVE) or DEFAULT_DNSRESOLVE
                             ): bool,
            }),
            errors=errors,
        )

    async def _async_controller_existed(self, host):
        existing_hosts = [entry.data.get(CONF_NAME) for entry in self._async_current_entries()]
        return host in existing_hosts

    async def _async_try_connect(self, host, username, password, timeout, verify_tls):
        http_session = async_get_clientsession(self.hass, verify_tls)
        logged = await login(host, username, password, timeout, http_session)
        return logged is not False


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
