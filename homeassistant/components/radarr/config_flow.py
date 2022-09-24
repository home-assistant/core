"""Config flow for Radarr."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientConnectorError
from aiopyarr import exceptions
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient
import voluptuous as vol
from yarl import URL

from homeassistant.components.hassio import ATTR_SLUG, get_addons_info, is_hassio
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_USE_ADDON, DEFAULT_NAME, DEFAULT_URL, DOMAIN, LOGGER

ON_SUPERVISOR_SCHEMA = vol.Schema({vol.Optional(CONF_USE_ADDON, default=True): bool})


class RadarrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radarr."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self.entry: ConfigEntry | None = None
        self._url: str | None = None

    async def async_step_reauth(self, _: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is not None:
            return await self.async_step_user()

        self._set_confirm_only()
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_user(self, _: dict[str, Any] | None = None) -> FlowResult:
        """Handle a flow initiated by the user."""
        if is_hassio(self.hass):
            for addon in get_addons_info(self.hass).values():
                if DOMAIN in addon[ATTR_SLUG]:
                    self._url = addon["network"]["7878/tcp"]
                    return await self.async_step_on_supervisor()
        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a manual flow initiated by the user."""
        errors = {}
        if user_input is None:
            user_input = dict(self.entry.data) if self.entry else None

        else:
            error, key = await self.validate_input(user_input)
            if error:
                errors = {"base": error}
            else:
                if self.entry:
                    self.hass.config_entries.async_update_entry(
                        self.entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(self.entry.entry_id)

                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_API_KEY: key} | user_input,
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL, default=user_input.get(CONF_URL, DEFAULT_URL)
                    ): str,
                    vol.Optional(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL, False),
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_KEY] == config[CONF_API_KEY]:
                _part = config[CONF_API_KEY][0:4]
                _msg = f"Radarr yaml config with partial key {_part} has been imported. Please remove it"
                LOGGER.warning(_msg)
                return self.async_abort(reason="already_configured")
        proto = "https" if config[CONF_SSL] else "http"
        host_port = f"{config[CONF_HOST]}:{config[CONF_PORT]}"
        path = ""
        if config["urlbase"].rstrip("/") not in ("", "/", "/api"):
            path = config["urlbase"].rstrip("/")
        return self.async_create_entry(
            title=DEFAULT_NAME,
            data={
                CONF_URL: f"{proto}://{host_port}{path}",
                CONF_API_KEY: config[CONF_API_KEY],
                CONF_VERIFY_SSL: False,
            },
        )

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle logic when on Supervisor host."""
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor", data_schema=ON_SUPERVISOR_SCHEMA
            )

        if not user_input[CONF_USE_ADDON]:
            return await self.async_step_manual()

        try:
            url = URL(get_url(self.hass, allow_ip=False))
            self._url = f"{url.scheme}://{url.host}:{self._url}"
        except NoURLAvailableError:
            self._url = f"http://homeassistant.local:{self._url}"
        _, key = await self.validate_input({CONF_URL: self._url})
        return self.async_create_entry(
            title=DEFAULT_NAME,
            data={CONF_URL: self._url, CONF_API_KEY: key, CONF_VERIFY_SSL: False},
        )

    async def validate_input(
        self, data: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Validate the user input allows us to connect."""
        host_configuration = PyArrHostConfiguration(
            api_token=data.get(CONF_API_KEY, ""),
            verify_ssl=data.get(CONF_VERIFY_SSL, False),
            url=data[CONF_URL],
        )
        radarr = RadarrClient(
            host_configuration=host_configuration,
            session=async_get_clientsession(self.hass),
        )
        try:
            if CONF_API_KEY not in data:
                result = await radarr.async_try_zeroconf()
                if isinstance(result, tuple):
                    self._url = f"{self._url}{result[2]}"
                    return None, result[1]
                return result, None
            await radarr.async_get_system_status()
        except exceptions.ArrAuthenticationException:
            return "invalid_auth", None
        except (ClientConnectorError, exceptions.ArrConnectionException):
            return "cannot_connect", None
        except exceptions.ArrException:
            return "unknown", None
        return None, None
