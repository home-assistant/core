"""Config flow for Remember The Milk integration."""

import asyncio
from collections.abc import Mapping
from typing import Any, override

from aiortm import AioRTMClient, AioRTMError, Auth, AuthError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_LIST_ID, CONF_SHARED_SECRET, DOMAIN, LOGGER, SUBENTRY_TYPE_LIST
from .coordinator import RememberTheMilkData

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

    @classmethod
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_LIST: ListSubentryFlowHandler}

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
            except AioRTMError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.async_step_auth()

        suggested_values: Mapping[str, Any] | None = user_input
        if suggested_values is None and self.source == SOURCE_REAUTH:
            suggested_values = self._get_reauth_entry().data
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
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
        except AioRTMError:
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
        or check_token.
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
        except AioRTMError:
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


class ListSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and reconfiguring RTM lists."""

    @property
    def _client(self) -> AioRTMClient:
        """Return the RTM client from the parent entry."""
        data: RememberTheMilkData = self._get_entry().runtime_data
        return data.client

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a new RTM list."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        errors: dict[str, str] = {}
        if user_input is not None:
            name: str = user_input[CONF_NAME]
            try:
                timeline_response = await self._client.rtm.timelines.create()
                list_response = await self._client.rtm.lists.add(
                    timeline=timeline_response.timeline,
                    name=name,
                )
            except AioRTMError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                new_list_id = list_response.list.id
                return self.async_create_entry(
                    title=name,
                    data={CONF_LIST_ID: new_list_id},
                    unique_id=str(new_list_id),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_NAME): TextSelector()}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Rename the RTM list on the server and update the sub-entry title."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            name: str = user_input[CONF_NAME]
            try:
                timeline_response = await self._client.rtm.timelines.create()
                await self._client.rtm.lists.set_name(
                    timeline=timeline_response.timeline,
                    list_id=subentry.data[CONF_LIST_ID],
                    name=name,
                )
            except AioRTMError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=name,
                    data=subentry.data,
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_NAME): TextSelector()}),
                {CONF_NAME: subentry.title},
            ),
            errors=errors,
        )
