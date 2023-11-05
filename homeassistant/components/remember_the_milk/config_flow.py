"""Config flow for Remember The Milk integration."""

import asyncio
from collections.abc import Mapping
from typing import Any, override

from aiortm import Auth, AuthError, ResponseError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_SHARED_SECRET, DOMAIN, LOGGER

TOKEN_TIMEOUT_SEC = 30

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_SHARED_SECRET): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
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
        self._auth_credentials: dict[str, str] | None = None

    def _get_auth(
        self, api_key: str, shared_secret: str, token: str | None = None
    ) -> Auth:
        """Return an Auth client for the given credentials."""
        return Auth(
            client_session=async_get_clientsession(self.hass),
            api_key=api_key,
            shared_secret=shared_secret,
            auth_token=token,
            permission="delete",
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._auth_credentials = user_input
            auth = self._auth = self._get_auth(
                user_input[CONF_API_KEY], user_input[CONF_SHARED_SECRET]
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
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                self._get_reauth_entry().data
                if self.source == SOURCE_REAUTH
                else user_input,
            ),
            errors=errors,
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
        assert self._auth_credentials is not None
        try:
            async with asyncio.timeout(TOKEN_TIMEOUT_SEC):
                token_data = await self._auth.get_token(self._frob)
        except TimeoutError:
            return self.async_abort(reason="timeout_token")
        except AuthError:
            return self.async_abort(reason="invalid_auth")
        except ResponseError:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001 pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return await self._async_create_entry(
            token_data,
            self._auth_credentials[CONF_API_KEY],
            self._auth_credentials[CONF_SHARED_SECRET],
        )

    async def _async_create_entry(
        self,
        token_data: dict[str, Any],
        api_key: str,
        shared_secret: str,
    ) -> ConfigFlowResult:
        """Create or update the config entry from token data.

        The token data has the same structure whether it comes from get_token
        or check_token. The username defaults to the Remember The Milk account
        username but can be overridden, e.g. to keep the YAML account name.
        """
        await self.async_set_unique_id(token_data["user"]["id"])
        data = {
            CONF_API_KEY: api_key,
            CONF_SHARED_SECRET: shared_secret,
            CONF_TOKEN: token_data["token"],
            CONF_USERNAME: token_data["user"]["username"],
        }
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=data,
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=token_data["user"]["fullname"],
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
        """Import a config entry from YAML.

        The token, looked up from legacy storage in async_setup, is passed in
        the import data. Without a valid token the import is aborted so the user
        sets the integration up via the UI. A repair issue is raised in
        async_setup for both the success and failure cases.
        """
        name = import_info.pop(CONF_NAME)
        self._async_abort_entries_match({CONF_USERNAME: name})
        token = import_info.get(CONF_TOKEN)
        if token is None:
            return self.async_abort(reason="invalid_auth")
        auth = self._get_auth(
            import_info[CONF_API_KEY], import_info[CONF_SHARED_SECRET], token
        )
        try:
            token_data = await auth.check_token()
        except AuthError:
            return self.async_abort(reason="invalid_auth")
        except ResponseError:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001 pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        if token_data["user"]["username"] != name:
            return self.async_abort(reason="invalid_auth")
        return await self._async_create_entry(
            token_data,
            import_info[CONF_API_KEY],
            import_info[CONF_SHARED_SECRET],
        )
