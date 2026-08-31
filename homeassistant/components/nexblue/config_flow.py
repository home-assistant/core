"""Config flow for the NexBlue integration."""

from typing import Any, override

from nexblue_api import (
    NexBlueAuthError,
    NexBlueClient,
    NexBlueConnectionError,
    NexBlueError,
    TokenBundle,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, DEFAULT_API_URL, DOMAIN, LOGGER

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class NexBlueConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a NexBlue config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial setup from the user interface."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token, error = await self._async_validate_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error:
                errors["base"] = error
            else:
                assert token is not None
                assert token.account_id is not None
                assert token.refresh_token is not None
                await self.async_set_unique_id(token.account_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"NexBlue ({user_input[CONF_USERNAME]})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REFRESH_TOKEN: token.refresh_token,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def _async_validate_login(
        self, username: str, password: str
    ) -> tuple[TokenBundle | None, str | None]:
        """Validate credentials and return token data safe to persist."""
        client = NexBlueClient(async_get_clientsession(self.hass), DEFAULT_API_URL)
        try:
            token = await client.async_login(username, password)
        except NexBlueAuthError:
            return None, "invalid_auth"
        except NexBlueConnectionError:
            return None, "cannot_connect"
        except NexBlueError:
            return None, "unknown"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error validating NexBlue credentials")
            return None, "unknown"

        if not token.refresh_token:
            return None, "invalid_auth"
        if not token.account_id:
            return None, "unknown"
        return token, None
