"""Config flow for Overkiz (by Somfy) integration."""
from __future__ import annotations

from typing import Any

from aiohttp import ClientError
from pyoverkiz.client import OverkizClient
from pyoverkiz.const import SUPPORTED_SERVERS
from pyoverkiz.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyRequestsException,
)
from pyoverkiz.models import obfuscate_id
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HUB, DEFAULT_HUB, DOMAIN, LOGGER


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Overkiz (by Somfy)."""

    VERSION = 1

    async def async_validate_input(self, user_input: dict[str, Any]) -> None:
        """Validate user credentials."""
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        server = SUPPORTED_SERVERS[user_input[CONF_HUB]]
        session = async_get_clientsession(self.hass)

        client = OverkizClient(
            username=username, password=password, server=server, session=session
        )

        await client.login()

        # Set first gateway id as unique id
        if gateways := await client.get_gateways():
            gateway_id = gateways[0].id
            await self.async_set_unique_id(gateway_id)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step via config flow."""
        errors = {}

        if user_input:
            try:
                await self.async_validate_input(user_input)
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except BadCredentialsException:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except MaintenanceException:
                errors["base"] = "server_in_maintenance"
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                LOGGER.exception(exception)
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_HUB, default=DEFAULT_HUB): vol.In(
                        {key: hub.name for key, hub in SUPPORTED_SERVERS.items()}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle DHCP discovery."""
        hostname = discovery_info.hostname
        gateway_id = hostname[8:22]

        LOGGER.debug("DHCP discovery detected gateway %s", obfuscate_id(gateway_id))

        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle ZeroConf discovery."""

        # abort if we already have exactly this bridge id/host
        properties = discovery_info.properties
        gateway_id = properties["gateway_pin"]

        LOGGER.debug("ZeroConf discovery detected gateway %s", obfuscate_id(gateway_id))

        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()
