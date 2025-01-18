"""Config flow for the MELCloud platform."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError
import pymelcloud
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _create_entry(self, username: str, token: str) -> ConfigFlowResult:
        """Register new entry."""
        await self.async_set_unique_id(username)
        self._abort_if_unique_id_configured({CONF_TOKEN: token})
        return self.async_create_entry(
            title=username, data={CONF_USERNAME: username, CONF_TOKEN: token}
        )

    async def _create_client(
        self,
        username: str,
        *,
        password: str | None = None,
        token: str | None = None,
    ) -> ConfigFlowResult:
        """Create client."""
        try:
            async with asyncio.timeout(10):
                if (acquired_token := token) is None:
                    acquired_token = await pymelcloud.login(
                        username,
                        password,
                        async_get_clientsession(self.hass),
                    )
                await pymelcloud.get_devices(
                    acquired_token,
                    async_get_clientsession(self.hass),
                )
        except ClientResponseError as err:
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                return self.async_abort(reason="invalid_auth")
            return self.async_abort(reason="cannot_connect")
        except (TimeoutError, ClientError):
            return self.async_abort(reason="cannot_connect")

        return await self._create_entry(username, acquired_token)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
                ),
            )
        username = user_input[CONF_USERNAME]
        return await self._create_client(username, password=user_input[CONF_PASSWORD])

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with MELCloud."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with MELCloud."""
        errors: dict[str, str] = {}

        if user_input is not None:
            aquired_token, errors = await self.async_reauthenticate_client(user_input)

            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data={CONF_TOKEN: aquired_token}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_reauthenticate_client(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, dict[str, str]]:
        """Reauthenticate with MELCloud."""
        errors: dict[str, str] = {}
        acquired_token = None

        try:
            async with asyncio.timeout(10):
                acquired_token = await pymelcloud.login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    async_get_clientsession(self.hass),
                )
        except (ClientResponseError, AttributeError) as err:
            if (
                isinstance(err, ClientResponseError)
                and err.status
                in (
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.FORBIDDEN,
                )
            ) or (isinstance(err, AttributeError) and err.name == "get"):
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "cannot_connect"
        except (
            TimeoutError,
            ClientError,
        ):
            errors["base"] = "cannot_connect"

        return acquired_token, errors

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors: dict[str, str] = {}
        acquired_token = None
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            user_input[CONF_USERNAME] = reconfigure_entry.data[CONF_USERNAME]
            try:
                async with asyncio.timeout(10):
                    acquired_token = await pymelcloud.login(
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        async_get_clientsession(self.hass),
                    )
            except (ClientResponseError, AttributeError) as err:
                if (
                    isinstance(err, ClientResponseError)
                    and err.status
                    in (
                        HTTPStatus.UNAUTHORIZED,
                        HTTPStatus.FORBIDDEN,
                    )
                ) or (isinstance(err, AttributeError) and err.name == "get"):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except (
                TimeoutError,
                ClientError,
            ):
                errors["base"] = "cannot_connect"

            if not errors:
                user_input[CONF_TOKEN] = acquired_token
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                CONF_USERNAME: reconfigure_entry.data[CONF_USERNAME]
            },
        )
