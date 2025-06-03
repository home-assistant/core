"""Config flow for Lidarr."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientConnectorError
from aiopyarr import exceptions
from aiopyarr.lidarr_client import LidarrClient
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DOMAIN


class LidarrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lidarr."""

    VERSION = 1

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
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

        if user_input is not None:
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
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=user_input
                    )

                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        if user_input is None:
            user_input = {}
            if self.source == SOURCE_REAUTH:
                user_input = dict(self._get_reauth_entry().data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): str,
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
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    lidarr = LidarrClient(
        api_token=data.get(CONF_API_KEY, ""),
        url=data[CONF_URL],
        session=async_get_clientsession(hass),
        verify_ssl=data[CONF_VERIFY_SSL],
    )
    if CONF_API_KEY not in data:
        return await lidarr.async_try_zeroconf()
    await lidarr.async_get_system_status()
    return None
