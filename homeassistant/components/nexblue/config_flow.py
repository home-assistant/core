"""Config flow for the NexBlue integration."""

from collections.abc import Mapping
from typing import Any, override

from nexblue_api import (
    NexBlueAuthError,
    NexBlueClient,
    NexBlueConnectionError,
    NexBlueError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, DEFAULT_API_URL, DOMAIN, LOGGER

AUTH_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

REAUTH_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
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
            result = await self._async_validate_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if isinstance(result, str):
                errors["base"] = result
            else:
                account_id, refresh_token = result
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"NexBlue ({user_input[CONF_USERNAME]})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data[CONF_USERNAME]

        if user_input is not None:
            result = await self._async_validate_login(
                username, user_input[CONF_PASSWORD]
            )
            if isinstance(result, str):
                errors["base"] = result
            else:
                account_id, refresh_token = result
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={CONF_USERNAME: username},
            errors=errors,
        )

    async def _async_validate_login(
        self, username: str, password: str
    ) -> tuple[str, str] | str:
        """Validate credentials and return the account ID and refresh token or an error key."""
        client = NexBlueClient(async_get_clientsession(self.hass), DEFAULT_API_URL)
        try:
            token = await client.async_login(username, password)
        except NexBlueAuthError:
            return "invalid_auth"
        except NexBlueConnectionError:
            return "cannot_connect"
        except NexBlueError:
            return "unknown"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error validating NexBlue credentials")
            return "unknown"

        if not token.refresh_token:
            return "invalid_auth"
        if not token.account_id:
            return "unknown"
        return token.account_id, token.refresh_token
