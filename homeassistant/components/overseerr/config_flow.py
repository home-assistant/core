"""Config flow for Overseerr."""

from collections.abc import Mapping
from typing import Any

from python_overseerr import (
    OverseerrAuthenticationError,
    OverseerrClient,
    OverseerrError,
)
import voluptuous as vol
from yarl import URL

from homeassistant.components.webhook import async_generate_id
from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_WEBHOOK_ID,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class OverseerrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Overseerr config flow."""

    async def _check_connection(
        self, host: str, port: int, ssl: bool, api_key: str
    ) -> str | None:
        """Check if we can connect to the Overseerr instance."""
        client = OverseerrClient(
            host,
            port,
            api_key,
            ssl=ssl,
            session=async_get_clientsession(self.hass),
        )
        try:
            await client.get_request_count()
        except OverseerrAuthenticationError:
            return "invalid_auth"
        except OverseerrError:
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            url = URL(user_input[CONF_URL])
            if (host := url.host) is None:
                errors[CONF_URL] = "invalid_host"
            else:
                self._async_abort_entries_match({CONF_HOST: host})
                port = url.port
                assert port
                error = await self._check_connection(
                    host, port, url.scheme == "https", user_input[CONF_API_KEY]
                )
                if error:
                    errors["base"] = error
                else:
                    if self.source == SOURCE_USER:
                        return self.async_create_entry(
                            title="Overseerr",
                            data={
                                CONF_HOST: host,
                                CONF_PORT: port,
                                CONF_SSL: url.scheme == "https",
                                CONF_API_KEY: user_input[CONF_API_KEY],
                                CONF_WEBHOOK_ID: async_generate_id(),
                            },
                        )
                    reconfigure_entry = self._get_reconfigure_entry()
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data={
                            **reconfigure_entry.data,
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_SSL: url.scheme == "https",
                            CONF_API_KEY: user_input[CONF_API_KEY],
                        },
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_URL): str, vol.Required(CONF_API_KEY): str}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth confirmation."""
        errors: dict[str, str] = {}
        if user_input:
            entry = self._get_reauth_entry()
            error = await self._check_connection(
                entry.data[CONF_HOST],
                entry.data[CONF_PORT],
                entry.data[CONF_SSL],
                user_input[CONF_API_KEY],
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()
