"""Adds config flow for Tibber integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import tibber
from tibber.data_api import TibberDataAPI
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    async_get_config_entry_implementation,
    async_get_implementations,
)
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    API_TYPE_DATA_API,
    API_TYPE_GRAPHQL,
    CONF_API_TYPE,
    DATA_API_DEFAULT_SCOPES,
    DOMAIN,
)

TYPE_SELECTOR = vol.Schema(
    {
        vol.Required(CONF_API_TYPE, default=API_TYPE_GRAPHQL): SelectSelector(
            SelectSelectorConfig(
                options=[API_TYPE_GRAPHQL, API_TYPE_DATA_API],
                translation_key="api_type",
            )
        )
    }
)

GRAPHQL_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})

ERR_TIMEOUT = "timeout"
ERR_CLIENT = "cannot_connect"
ERR_TOKEN = "invalid_access_token"
TOKEN_URL = "https://developer.tibber.com/settings/access-token"
DATA_API_DOC_URL = "https://data-api.tibber.com/docs/auth/"
APPLICATION_CREDENTIALS_DOC_URL = (
    "https://www.home-assistant.io/integrations/application_credentials/"
)

_LOGGER = logging.getLogger(__name__)


class TibberConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Tibber integration."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._api_type: str | None = None
        self._data_api_home_ids: list[str] = []
        self._data_api_user_sub: str | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data appended to the authorize URL."""
        if self._api_type != API_TYPE_DATA_API:
            return super().extra_authorize_data
        return {
            **super().extra_authorize_data,
            "scope": " ".join(DATA_API_DEFAULT_SCOPES),
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=TYPE_SELECTOR,
                description_placeholders={"url": DATA_API_DOC_URL},
            )

        self._api_type = user_input[CONF_API_TYPE]

        if self._api_type == API_TYPE_GRAPHQL:
            return await self.async_step_graphql()

        return await self.async_step_data_api()

    async def async_step_graphql(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle GraphQL token based configuration."""

        if self.source != SOURCE_REAUTH:
            for entry in self._async_current_entries(include_ignore=False):
                if entry.entry_id == self.context.get("entry_id"):
                    continue
                if entry.data.get(CONF_API_TYPE, API_TYPE_GRAPHQL) == API_TYPE_GRAPHQL:
                    return self.async_abort(reason="already_configured")

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN].replace(" ", "")

            tibber_connection = tibber.Tibber(
                access_token=access_token,
                websession=async_get_clientsession(self.hass),
            )

            errors = {}

            try:
                await tibber_connection.update_info()
            except TimeoutError:
                errors[CONF_ACCESS_TOKEN] = ERR_TIMEOUT
            except tibber.InvalidLoginError:
                errors[CONF_ACCESS_TOKEN] = ERR_TOKEN
            except (
                aiohttp.ClientError,
                tibber.RetryableHttpExceptionError,
                tibber.FatalHttpExceptionError,
            ):
                errors[CONF_ACCESS_TOKEN] = ERR_CLIENT

            if errors:
                return self.async_show_form(
                    step_id="graphql",
                    data_schema=GRAPHQL_SCHEMA,
                    description_placeholders={"url": TOKEN_URL},
                    errors=errors,
                )

            unique_id = tibber_connection.user_id
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            data = {
                CONF_API_TYPE: API_TYPE_GRAPHQL,
                CONF_ACCESS_TOKEN: access_token,
            }

            return self.async_create_entry(
                title=tibber_connection.name,
                data=data,
            )

        return self.async_show_form(
            step_id="graphql",
            data_schema=GRAPHQL_SCHEMA,
            description_placeholders={"url": TOKEN_URL},
            errors={},
        )

    async def async_step_data_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the Data API OAuth configuration."""

        implementations = await async_get_implementations(self.hass, self.DOMAIN)
        if not implementations:
            return self.async_abort(
                reason="missing_credentials",
                description_placeholders={
                    "application_credentials_url": APPLICATION_CREDENTIALS_DOC_URL,
                    "data_api_url": DATA_API_DOC_URL,
                },
            )

        return await self.async_step_pick_implementation(user_input)

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Finalize the OAuth flow and create the config entry."""

        assert self._api_type == API_TYPE_DATA_API

        token: dict[str, Any] = data["token"]

        client = TibberDataAPI(
            token[CONF_ACCESS_TOKEN],
            websession=async_get_clientsession(self.hass),
        )

        try:
            userinfo = await client.get_userinfo()
        except (
            tibber.InvalidLoginError,
            tibber.FatalHttpExceptionError,
        ) as err:
            self.logger.error("Authentication failed against Data API: %s", err)
            return self.async_abort(reason="oauth_invalid_token")
        except (aiohttp.ClientError, TimeoutError) as err:
            self.logger.error("Error retrieving homes via Data API: %s", err)
            return self.async_abort(reason="cannot_connect")

        unique_id = userinfo["email"]
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        entry_data: dict[str, Any] = {
            CONF_API_TYPE: API_TYPE_DATA_API,
            "auth_implementation": data["auth_implementation"],
            CONF_TOKEN: token,
        }

        title = userinfo["email"]
        return self.async_create_entry(
            title=title,
            data=entry_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""

        api_type = entry_data.get(CONF_API_TYPE, API_TYPE_GRAPHQL)
        self._api_type = api_type

        if api_type == API_TYPE_DATA_API:
            self.flow_impl = await async_get_config_entry_implementation(
                self.hass, self._get_reauth_entry()
            )
            return await self.async_step_auth()

        self.context["title_placeholders"] = {"name": self._get_reauth_entry().title}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the reauth dialog for GraphQL entries."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        return await self.async_step_graphql()
