"""Config flow for YouTube integration."""
from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping
import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlowWithConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CHANNEL_CREATION_HELP_URL,
    CONF_CHANNELS,
    DEFAULT_ACCESS,
    DOMAIN,
    LOGGER,
)


async def _get_subscriptions(hass: HomeAssistant, resource: Resource) -> AsyncGenerator:
    amount_of_subscriptions = 50
    received_amount_of_subscriptions = 0
    next_page_token = None
    while received_amount_of_subscriptions < amount_of_subscriptions:
        # pylint: disable=no-member
        subscription_request: HttpRequest = resource.subscriptions().list(
            part="snippet", mine=True, maxResults=50, pageToken=next_page_token
        )
        res = await hass.async_add_executor_job(subscription_request.execute)
        amount_of_subscriptions = res["pageInfo"]["totalResults"]
        if "nextPageToken" in res:
            next_page_token = res["nextPageToken"]
        for item in res["items"]:
            received_amount_of_subscriptions += 1
            yield item


async def get_resource(hass: HomeAssistant, token: str) -> Resource:
    """Get Youtube resource async."""

    def _build_resource() -> Resource:
        return build(
            "youtube",
            "v3",
            credentials=Credentials(token),
        )

    return await hass.async_add_executor_job(_build_resource)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google OAuth2 authentication."""

    _data: dict[str, Any] = {}
    _title: str = ""

    DOMAIN = DOMAIN

    reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> YouTubeOptionsFlowHandler:
        """Get the options flow for this handler."""
        return YouTubeOptionsFlowHandler(config_entry)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(DEFAULT_ACCESS),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""
        try:
            service = await get_resource(self.hass, data[CONF_TOKEN][CONF_ACCESS_TOKEN])
            # pylint: disable=no-member
            own_channel_request: HttpRequest = service.channels().list(
                part="snippet", mine=True
            )
            response = await self.hass.async_add_executor_job(
                own_channel_request.execute
            )
            if not response["items"]:
                return self.async_abort(
                    reason="no_channel",
                    description_placeholders={"support_url": CHANNEL_CREATION_HELP_URL},
                )
            own_channel = response["items"][0]
        except HttpError as ex:
            error = ex.reason
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": error},
            )
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.error("Unknown error occurred: %s", ex.args)
            return self.async_abort(reason="unknown")
        self._title = own_channel["snippet"]["title"]
        self._data = data

        if not self.reauth_entry:
            await self.async_set_unique_id(own_channel["id"])
            self._abort_if_unique_id_configured()

            return await self.async_step_channels()

        if self.reauth_entry.unique_id == own_channel["id"]:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_abort(
            reason="wrong_account",
            description_placeholders={"title": self._title},
        )

    async def async_step_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which channels to track."""
        if user_input:
            return self.async_create_entry(
                title=self._title,
                data=self._data,
                options=user_input,
            )
        service = await get_resource(
            self.hass, self._data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        selectable_channels = [
            SelectOptionDict(
                value=subscription["snippet"]["resourceId"]["channelId"],
                label=subscription["snippet"]["title"],
            )
            async for subscription in _get_subscriptions(self.hass, service)
        ]
        return self.async_show_form(
            step_id="channels",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHANNELS): SelectSelector(
                        SelectSelectorConfig(options=selectable_channels, multiple=True)
                    ),
                }
            ),
        )


class YouTubeOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """YouTube Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize form."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title,
                data=user_input,
            )
        service = await get_resource(
            self.hass, self.config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        selectable_channels = [
            SelectOptionDict(
                value=subscription["snippet"]["resourceId"]["channelId"],
                label=subscription["snippet"]["title"],
            )
            async for subscription in _get_subscriptions(self.hass, service)
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_CHANNELS): SelectSelector(
                            SelectSelectorConfig(
                                options=selectable_channels, multiple=True
                            )
                        ),
                    }
                ),
                self.options,
            ),
        )
