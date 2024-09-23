"""Config flow for Radarr."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientConnectorError
from aiopyarr import exceptions
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import RadarrConfigEntry
from .const import DEFAULT_NAME, DEFAULT_URL, DOMAIN


class RadarrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radarr."""

    VERSION = 1
    entry: RadarrConfigEntry | None = None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is not None:
            return await self.async_step_user()

        self._set_confirm_only()
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            user_input = dict(self.entry.data) if self.entry else None

        else:
            try:
                if result := await validate_input(self.hass, user_input):
                    user_input[CONF_API_KEY] = result[1]
            except exceptions.ArrAuthenticationException:
                errors = {"base": "invalid_auth"}
            except (ClientConnectorError, exceptions.ArrConnectionException):
                errors = {"base": "cannot_connect"}
            except exceptions.ArrWrongAppException:
                errors = {"base": "wrong_app"}
            except exceptions.ArrZeroConfException:
                errors = {"base": "zeroconf_failed"}
            except exceptions.ArrException:
                errors = {"base": "unknown"}
            if not errors:
                if self.entry:
                    self.hass.config_entries.async_update_entry(
                        self.entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(self.entry.entry_id)

                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
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


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[str, str, str] | None:
    """Validate the user input allows us to connect."""
    host_configuration = PyArrHostConfiguration(
        api_token=data.get(CONF_API_KEY, ""),
        verify_ssl=data[CONF_VERIFY_SSL],
        url=data[CONF_URL],
    )
    radarr = RadarrClient(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass),
    )
    if CONF_API_KEY not in data:
        return await radarr.async_try_zeroconf()
    await radarr.async_get_system_status()
    return None
