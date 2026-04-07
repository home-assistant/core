"""Config flow for Matrix integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from nio import AsyncClient, LoginError, WhoamiError, WhoamiResponse
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL

from .const import CONF_HOMESERVER, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOMESERVER): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _try_login(
    homeserver: str, username: str, password: str, verify_ssl: bool
) -> tuple[str | None, str | None]:
    """Try to log in to the Matrix homeserver.

    Returns (error_key, user_id) where error_key is None on success.
    """
    client = AsyncClient(homeserver=homeserver, user=username, ssl=verify_ssl)
    try:
        response = await client.login(password=password)
        if isinstance(response, LoginError):
            _LOGGER.debug("Login failed: %s %s", response.status_code, response.message)
            return "invalid_auth", None

        # Verify we got a valid user_id back
        whoami_response = await client.whoami()
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Exception during Matrix login attempt", exc_info=True)
        return "cannot_connect", None
    else:
        if isinstance(whoami_response, WhoamiError):
            return "invalid_auth", None

        if isinstance(whoami_response, WhoamiResponse):
            return None, whoami_response.user_id

        return "invalid_auth", None
    finally:
        await client.close()


class MatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Matrix."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error, user_id = await _try_login(
                user_input[CONF_HOMESERVER],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input.get(CONF_VERIFY_SSL, True),
            )
            if error is not None:
                errors["base"] = error
            elif user_id is not None:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_id,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation dialog."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            new_data = {**reauth_entry.data, **user_input}
            error, user_id = await _try_login(
                new_data[CONF_HOMESERVER],
                new_data[CONF_USERNAME],
                new_data[CONF_PASSWORD],
                new_data.get(CONF_VERIFY_SSL, True),
            )
            if error is not None:
                errors["base"] = error
            elif user_id is not None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data=new_data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={
                "username": reauth_entry.data[CONF_USERNAME],
                "homeserver": reauth_entry.data[CONF_HOMESERVER],
            },
        )
