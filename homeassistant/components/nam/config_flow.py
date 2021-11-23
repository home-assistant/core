"""Adds config flow for Nettigo Air Monitor."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
import async_timeout
from nettigo_air_monitor import (
    ApiError,
    AuthFailed,
    CannotGetMac,
    ConnectionOptions,
    NettigoAirMonitor,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def async_get_mac(hass: HomeAssistant, host: str, data: dict[str, Any]) -> str:
    """Get device MAC address."""
    websession = async_get_clientsession(hass)

    options = ConnectionOptions(host, data.get(CONF_USERNAME), data.get(CONF_PASSWORD))
    nam = await NettigoAirMonitor.create(websession, options)
    # Device firmware uses synchronous code and doesn't respond to http queries
    # when reading data from sensors. The nettigo-air-monitor library tries to get
    # the data 4 times, so we use a longer than usual timeout here.
    async with async_timeout.timeout(30):
        return await nam.async_get_mac_address()


class NAMFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nettigo Air Monitor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self.host: str
        self.entry: config_entries.ConfigEntry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST]

            try:
                mac = await async_get_mac(self.hass, self.host, {})
            except AuthFailed:
                return await self.async_step_credentials()
            except (ApiError, ClientConnectorError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except CannotGetMac:
                return self.async_abort(reason="device_unsupported")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(format_mac(mac))
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                return self.async_create_entry(
                    title=self.host,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                mac = await async_get_mac(self.hass, self.host, user_input)
            except AuthFailed:
                errors["base"] = "invalid_auth"
            except (ApiError, ClientConnectorError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except CannotGetMac:
                return self.async_abort(reason="device_unsupported")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(format_mac(mac))
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                return self.async_create_entry(
                    title=self.host,
                    data={**user_input, CONF_HOST: self.host},
                )

        return self.async_show_form(
            step_id="credentials", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info[zeroconf.ATTR_HOST]
        self.context["title_placeholders"] = {"host": self.host}

        # Do not probe the device if the host is already configured
        self._async_abort_entries_match({CONF_HOST: self.host})

        try:
            mac = await async_get_mac(self.hass, self.host, {})
        except AuthFailed:
            return await self.async_step_credentials()
        except (ApiError, ClientConnectorError, asyncio.TimeoutError):
            return self.async_abort(reason="cannot_connect")
        except CannotGetMac:
            return self.async_abort(reason="device_unsupported")

        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured({CONF_HOST: self.host})

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle discovery confirm."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=self.host,
                data={CONF_HOST: self.host},
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={"host": self.host},
            errors=errors,
        )

    async def async_step_reauth(self, data: dict[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        if entry := self.hass.config_entries.async_get_entry(self.context["entry_id"]):
            self.entry = entry
        self.host = data[CONF_HOST]
        self.context["title_placeholders"] = {"host": self.host}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await async_get_mac(self.hass, self.host, user_input)
            except (ApiError, AuthFailed, ClientConnectorError, asyncio.TimeoutError):
                return self.async_abort(reason="reauth_unsuccessful")
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry, data={**user_input, CONF_HOST: self.host}
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"host": self.host},
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )
