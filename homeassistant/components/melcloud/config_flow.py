"""Config flow for the MELCloud platform."""
from __future__ import annotations

import asyncio

from aiohttp import ClientError, ClientResponseError
from async_timeout import timeout
import pymelcloud
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    HTTP_FORBIDDEN,
    HTTP_UNAUTHORIZED,
)

from .const import DOMAIN


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _create_entry(self, username: str, token: str):
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
    ):
        """Create client."""
        if password is None and token is None:
            raise ValueError(
                "Invalid internal state. Called without either password or token"
            )

        try:
            with timeout(10):
                acquired_token = token
                if acquired_token is None:
                    acquired_token = await pymelcloud.login(
                        username,
                        password,
                        self.hass.helpers.aiohttp_client.async_get_clientsession(),
                    )
                await pymelcloud.get_devices(
                    acquired_token,
                    self.hass.helpers.aiohttp_client.async_get_clientsession(),
                )
        except ClientResponseError as err:
            if err.status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
                return self.async_abort(reason="invalid_auth")
            return self.async_abort(reason="cannot_connect")
        except (asyncio.TimeoutError, ClientError):
            return self.async_abort(reason="cannot_connect")

        return await self._create_entry(username, acquired_token)

    async def async_step_user(self, user_input=None):
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

    async def async_step_import(self, user_input):
        """Import a config entry."""
        return await self._create_client(
            user_input[CONF_USERNAME], token=user_input[CONF_TOKEN]
        )
