"""Config flow for YouTube integration."""
from __future__ import annotations

import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_CHANNELS, DEFAULT_ACCESS, DOMAIN, LOGGER


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google OAuth2 authentication."""

    _data: dict[str, Any] = {}
    _title: str = ""

    DOMAIN = DOMAIN

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

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""
        try:
            service = await self._get_resource(data[CONF_TOKEN][CONF_ACCESS_TOKEN])
            # pylint: disable=no-member
            own_channel_request: HttpRequest = service.channels().list(
                part="snippet", mine=True
            )
            response = await self.hass.async_add_executor_job(
                own_channel_request.execute
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

        await self.async_set_unique_id(own_channel["id"])
        self._abort_if_unique_id_configured()

        return await self.async_step_channels()

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
        service = await self._get_resource(self._data[CONF_TOKEN][CONF_ACCESS_TOKEN])
        # pylint: disable=no-member
        subscription_request: HttpRequest = service.subscriptions().list(
            part="snippet", mine=True, maxResults=50
        )
        response = await self.hass.async_add_executor_job(subscription_request.execute)
        selectable_channels = [
            SelectOptionDict(
                value=subscription["snippet"]["resourceId"]["channelId"],
                label=subscription["snippet"]["title"],
            )
            for subscription in response["items"]
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

    async def _get_resource(self, token: str) -> Resource:
        def _build_resource() -> Resource:
            return build(
                "youtube",
                "v3",
                credentials=Credentials(token),
            )

        return await self.hass.async_add_executor_job(_build_resource)
