"""Config flow for the MELCloud platform."""
import asyncio
import logging
from typing import Optional

from aiohttp import ClientError, ClientResponseError
from async_timeout import timeout
import pymelcloud
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register("melcloud")
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _create_entry(self, email: str, token: str):
        """Register new entry."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_EMAIL, entry.title) == email:
                entry.connection_class = self.CONNECTION_CLASS
                self.hass.config_entries.async_update_entry(
                    entry, data={CONF_EMAIL: email, CONF_TOKEN: token}
                )
                return self.async_abort(
                    reason="already_configured",
                    description_placeholders={"email": email},
                )

        return self.async_create_entry(
            title=email, data={CONF_EMAIL: email, CONF_TOKEN: token},
        )

    async def _create_client(
        self,
        email: str,
        *,
        password: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """Create client."""
        if password is None and token is None:
            raise ValueError(
                "Invalid internal state. Called without either password or token",
            )

        try:
            with timeout(10):
                acquired_token = token
                if acquired_token is None:
                    acquired_token = await pymelcloud.login(
                        email,
                        password,
                        self.hass.helpers.aiohttp_client.async_get_clientsession(),
                    )
                await pymelcloud.get_devices(
                    acquired_token,
                    self.hass.helpers.aiohttp_client.async_get_clientsession(),
                )
        except ClientResponseError as err:
            if err.status == 401 or err.status == 403:
                return self.async_abort(reason="invalid_auth")
            return self.async_abort(reason="cannot_connect")
        except (asyncio.TimeoutError, ClientError):
            return self.async_abort(reason="cannot_connect")

        return await self._create_entry(email, acquired_token)

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
                ),
            )
        email = user_input[CONF_EMAIL]
        return await self._create_client(email, password=user_input[CONF_PASSWORD],)

    async def async_step_import(self, user_input):
        """Import a config entry."""
        email = user_input.get(CONF_EMAIL)
        token = user_input.get(CONF_TOKEN)
        if not token:
            return await self.async_step_user()
        return await self._create_client(email, token=token,)
