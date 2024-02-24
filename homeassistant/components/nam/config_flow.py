"""Adds config flow for Nettigo Air Monitor."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from nettigo_air_monitor import (
    ApiError,
    AuthFailedError,
    CannotGetMacError,
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


@dataclass
class NamConfig:
    """NAM device configuration class."""

    mac_address: str
    auth_enabled: bool


_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def async_get_config(hass: HomeAssistant, host: str) -> NamConfig:
    """Get device MAC address and auth_enabled property."""
    websession = async_get_clientsession(hass)

    options = ConnectionOptions(host)
    nam = await NettigoAirMonitor.create(websession, options)

    async with asyncio.timeout(10):
        mac = await nam.async_get_mac_address()

    return NamConfig(mac, nam.auth_enabled)


async def async_check_credentials(
    hass: HomeAssistant, host: str, data: dict[str, Any]
) -> None:
    """Check if credentials are valid."""
    websession = async_get_clientsession(hass)

    options = ConnectionOptions(host, data.get(CONF_USERNAME), data.get(CONF_PASSWORD))

    nam = await NettigoAirMonitor.create(websession, options)

    async with asyncio.timeout(10):
        await nam.async_check_credentials()


class NAMFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nettigo Air Monitor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self.host: str
        self.entry: config_entries.ConfigEntry
        self._config: NamConfig

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.host = user_input[CONF_HOST]

            try:
                config = await async_get_config(self.hass, self.host)
            except (ApiError, ClientConnectorError, TimeoutError):
                errors["base"] = "cannot_connect"
            except CannotGetMacError:
                return self.async_abort(reason="device_unsupported")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(format_mac(config.mac_address))
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                if config.auth_enabled is True:
                    return await self.async_step_credentials()

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
                await async_check_credentials(self.hass, self.host, user_input)
            except AuthFailedError:
                errors["base"] = "invalid_auth"
            except (ApiError, ClientConnectorError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
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
        self.host = discovery_info.host
        self.context["title_placeholders"] = {"host": self.host}

        # Do not probe the device if the host is already configured
        self._async_abort_entries_match({CONF_HOST: self.host})

        try:
            self._config = await async_get_config(self.hass, self.host)
        except (ApiError, ClientConnectorError, TimeoutError):
            return self.async_abort(reason="cannot_connect")
        except CannotGetMacError:
            return self.async_abort(reason="device_unsupported")

        await self.async_set_unique_id(format_mac(self._config.mac_address))
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

        if self._config.auth_enabled is True:
            return await self.async_step_credentials()

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={"host": self.host},
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        if entry := self.hass.config_entries.async_get_entry(self.context["entry_id"]):
            self.entry = entry
        self.host = entry_data[CONF_HOST]
        self.context["title_placeholders"] = {"host": self.host}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await async_check_credentials(self.hass, self.host, user_input)
            except (
                ApiError,
                AuthFailedError,
                ClientConnectorError,
                TimeoutError,
            ):
                return self.async_abort(reason="reauth_unsuccessful")

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
