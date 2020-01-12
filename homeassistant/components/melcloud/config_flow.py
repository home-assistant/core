"""Config flow for the MELCloud platform."""
import asyncio
import logging
from typing import Callable

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
            title=email, data={CONF_EMAIL: email, CONF_TOKEN: token}
        )

    async def _init_client(self, email: str, password: str) -> pymelcloud.Client:
        return await pymelcloud.login(
            email, password, self.hass.helpers.aiohttp_client.async_get_clientsession(),
        )

    async def _init_client_with_token(self, token: str) -> pymelcloud.Client:
        return pymelcloud.Client(
            token, self.hass.helpers.aiohttp_client.async_get_clientsession(),
        )

    async def _create_client(
        self, email: str, client_creator: Callable[[], pymelcloud.Client],
    ):
        """Create client."""
        try:
            client = await client_creator()
            with timeout(10):
                await client.update_confs()
        except asyncio.TimeoutError:
            return self.async_abort(reason="cannot_connect")
        except ClientResponseError as err:
            if err.status == 401 or err.status == 403:
                return self.async_abort(reason="invalid_auth")
            return self.async_abort(reason="cannot_connect")
        except ClientError:
            _LOGGER.exception("ClientError")
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error creating device")
            return self.async_abort(reason="unknown")

        return await self._create_entry(email, client.token)

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
        return await self._create_client(
            email, lambda: self._init_client(email, user_input[CONF_PASSWORD])
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        email = user_input.get(CONF_EMAIL)
        token = user_input.get(CONF_TOKEN)
        if not token:
            return await self.async_step_user()
        return await self._create_client(
            email, lambda: self._init_client_with_token(token)
        )
