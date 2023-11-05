"""Config flow for Remember The Milk integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from aiortm import Auth, AuthError, ResponseError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SHARED_SECRET, DOMAIN, LOGGER

TOKEN_TIMEOUT_SEC = 30

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_SHARED_SECRET): str,
    }
)


class RTMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remember The Milk."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._auth: Auth | None = None
        self._url: str | None = None
        self._frob: str | None = None
        self._auth_data: dict[str, str] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._auth_data = user_input
            auth = self._auth = Auth(
                client_session=async_get_clientsession(self.hass),
                api_key=user_input[CONF_API_KEY],
                shared_secret=user_input[CONF_SHARED_SECRET],
                permission="delete",
            )
            try:
                self._url, self._frob = await auth.authenticate_desktop()
            except AuthError:
                errors["base"] = "invalid_auth"
            except ResponseError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.async_step_auth()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authorize the application."""
        assert self._url is not None
        if user_input is not None:
            return await self._get_token()

        return self.async_show_form(
            step_id="auth", description_placeholders={"url": self._url}
        )

    async def _get_token(self) -> ConfigFlowResult:
        """Get token and create config entry."""
        assert self._auth is not None
        assert self._frob is not None
        assert self._auth_data is not None
        try:
            async with asyncio.timeout(TOKEN_TIMEOUT_SEC):
                token = await self._auth.get_token(self._frob)
        except TimeoutError:
            return self.async_abort(reason="timeout_token")
        except AuthError:
            return self.async_abort(reason="invalid_auth")
        except ResponseError:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001 pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(token["user"]["id"])
        data = {
            **self._auth_data,
            CONF_TOKEN: token["token"],
            CONF_USERNAME: token["user"]["username"],
        }
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            if reauth_entry.source == SOURCE_IMPORT and reauth_entry.unique_id is None:
                # Imported entries do not have a token nor unique id.
                # Update unique id to match the new token.
                # This case can be removed when the import step is removed.
                self.hass.config_entries.async_update_entry(
                    reauth_entry, data=data, unique_id=token["user"]["id"]
                )
            else:
                self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=data,
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=token["user"]["fullname"],
            data=data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry.

        The token will be retrieved after config entry setup in a reauth flow.
        """
        name = import_info.pop(CONF_NAME)
        return self.async_create_entry(
            title=name,
            data=import_info | {CONF_USERNAME: name, CONF_TOKEN: None},
        )
