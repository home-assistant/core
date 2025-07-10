"""Slack platform for notify component."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, TypedDict, cast
from urllib.parse import urlparse

from aiohttp import BasicAuth
from aiohttp.client_exceptions import ClientError
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    BaseNotificationService,
)
from homeassistant.const import ATTR_ICON, CONF_PATH
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, config_validation as cv, template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_BLOCKS,
    ATTR_BLOCKS_TEMPLATE,
    ATTR_FILE,
    ATTR_PASSWORD,
    ATTR_PATH,
    ATTR_THREAD_TS,
    ATTR_URL,
    ATTR_USERNAME,
    CONF_DEFAULT_CHANNEL,
    DATA_CLIENT,
    SLACK_DATA,
)
from .utils import upload_file_to_slack

_LOGGER = logging.getLogger(__name__)

FILE_PATH_SCHEMA = vol.Schema({vol.Required(CONF_PATH): cv.isfile})

FILE_URL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URL): cv.url,
        vol.Inclusive(ATTR_USERNAME, "credentials"): cv.string,
        vol.Inclusive(ATTR_PASSWORD, "credentials"): cv.string,
    }
)

DATA_FILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FILE): vol.Any(FILE_PATH_SCHEMA, FILE_URL_SCHEMA),
        vol.Optional(ATTR_THREAD_TS): cv.string,
    }
)

DATA_TEXT_ONLY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_USERNAME): cv.string,
        vol.Optional(ATTR_ICON): cv.string,
        vol.Optional(ATTR_BLOCKS): list,
        vol.Optional(ATTR_BLOCKS_TEMPLATE): list,
        vol.Optional(ATTR_THREAD_TS): cv.string,
    }
)

DATA_SCHEMA = vol.All(
    cv.ensure_list, [vol.Any(DATA_FILE_SCHEMA, DATA_TEXT_ONLY_SCHEMA)]
)


class AuthDictT(TypedDict, total=False):
    """Type for auth request data."""

    auth: BasicAuth


class FormDataT(TypedDict, total=False):
    """Type for form data, file upload."""

    channels: str
    filename: str
    initial_comment: str
    title: str
    token: str
    thread_ts: str  # Optional key


class MessageT(TypedDict, total=False):
    """Type for message data."""

    link_names: bool
    text: str
    username: str  # Optional key
    icon_url: str  # Optional key
    icon_emoji: str  # Optional key
    blocks: list[Any]  # Optional key
    thread_ts: str  # Optional key


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SlackNotificationService | None:
    """Set up the Slack notification service."""
    if discovery_info:
        return SlackNotificationService(
            hass,
            discovery_info[SLACK_DATA][DATA_CLIENT],
            discovery_info,
        )
    return None


@callback
def _async_get_filename_from_url(url: str) -> str:
    """Return the filename of a passed URL."""
    parsed_url = urlparse(url)
    return os.path.basename(parsed_url.path)


@callback
def _async_sanitize_channel_names(channel_list: list[str]) -> list[str]:
    """Remove any # symbols from a channel list."""
    return [channel.lstrip("#") for channel in channel_list]


class SlackNotificationService(BaseNotificationService):
    """Define the Slack notification logic."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AsyncWebClient,
        config: dict[str, str],
    ) -> None:
        """Initialize."""
        self._hass = hass
        self._client = client
        self._config = config

    async def _async_send_local_file_message(
        self,
        path: str,
        targets: list[str],
        message: str,
        title: str | None,
        thread_ts: str | None,
    ) -> None:
        """Upload a local file (with message) to Slack."""
        if not self._hass.config.is_allowed_path(path):
            _LOGGER.error("Path does not exist or is not allowed: %s", path)
            return

        parsed_url = urlparse(path)
        filename = os.path.basename(parsed_url.path)

        channel_ids = [await self._async_get_channel_id(target) for target in targets]
        channel_ids = [cid for cid in channel_ids if cid]  # Remove None values

        if not channel_ids:
            _LOGGER.error("No valid channel IDs resolved for targets: %s", targets)
            return

        await upload_file_to_slack(
            client=self._client,
            channel_ids=channel_ids,
            file_content=None,
            file_path=path,
            filename=filename,
            title=title,
            message=message,
            thread_ts=thread_ts,
        )

    async def _async_send_remote_file_message(
        self,
        url: str,
        targets: list[str],
        message: str,
        title: str | None,
        thread_ts: str | None,
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Upload a remote file (with message) to Slack."""
        if not self._hass.config.is_allowed_external_url(url):
            _LOGGER.error("URL is not allowed: %s", url)
            return

        filename = _async_get_filename_from_url(url)
        session = aiohttp_client.async_get_clientsession(self._hass)

        # Fetch the remote file
        kwargs: AuthDictT = {}
        if username and password:
            kwargs = {"auth": BasicAuth(username, password=password)}

        try:
            async with session.get(url, **kwargs) as resp:
                resp.raise_for_status()
                file_content = await resp.read()
        except ClientError as err:
            _LOGGER.error("Error while retrieving %s: %r", url, err)
            return

        channel_ids = [await self._async_get_channel_id(target) for target in targets]
        channel_ids = [cid for cid in channel_ids if cid]  # Remove None values

        if not channel_ids:
            _LOGGER.error("No valid channel IDs resolved for targets: %s", targets)
            return

        await upload_file_to_slack(
            client=self._client,
            channel_ids=channel_ids,
            file_content=file_content,
            filename=filename,
            title=title,
            message=message,
            thread_ts=thread_ts,
        )

    async def _async_send_text_only_message(
        self,
        targets: list[str],
        message: str,
        title: str | None,
        thread_ts: str | None,
        *,
        username: str | None = None,
        icon: str | None = None,
        blocks: Any | None = None,
    ) -> None:
        """Send a text-only message."""
        message_dict: MessageT = {"link_names": True, "text": message}

        if username:
            message_dict["username"] = username

        if icon:
            if icon.lower().startswith(("http://", "https://")):
                message_dict["icon_url"] = icon
            else:
                message_dict["icon_emoji"] = icon

        if blocks:
            message_dict["blocks"] = blocks

        if thread_ts:
            message_dict["thread_ts"] = thread_ts

        tasks = {
            target: self._client.chat_postMessage(**message_dict, channel=target)
            for target in targets
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for target, result in zip(tasks, results, strict=False):
            if isinstance(result, SlackApiError):
                _LOGGER.error(
                    "There was a Slack API error while sending to %s: %r",
                    target,
                    result,
                )
            elif isinstance(result, ClientError):
                _LOGGER.error("Error while sending message to %s: %r", target, result)

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to Slack."""
        data = kwargs.get(ATTR_DATA) or {}

        try:
            DATA_SCHEMA(data)
        except vol.Invalid as err:
            _LOGGER.error("Invalid message data: %s", err)
            data = {}

        title = kwargs.get(ATTR_TITLE)
        targets = _async_sanitize_channel_names(
            kwargs.get(ATTR_TARGET, [self._config[CONF_DEFAULT_CHANNEL]])
        )

        # Message Type 1: A text-only message
        if ATTR_FILE not in data:
            if ATTR_BLOCKS_TEMPLATE in data:
                value = cv.template_complex(data[ATTR_BLOCKS_TEMPLATE])
                blocks = template.render_complex(value)
            elif ATTR_BLOCKS in data:
                blocks = data[ATTR_BLOCKS]
            else:
                blocks = None

            return await self._async_send_text_only_message(
                targets,
                message,
                title,
                username=data.get(ATTR_USERNAME, self._config.get(ATTR_USERNAME)),
                icon=data.get(ATTR_ICON, self._config.get(ATTR_ICON)),
                thread_ts=data.get(ATTR_THREAD_TS),
                blocks=blocks,
            )

        # Message Type 2: A message that uploads a remote file
        if ATTR_URL in data[ATTR_FILE]:
            return await self._async_send_remote_file_message(
                data[ATTR_FILE][ATTR_URL],
                targets,
                message,
                title,
                thread_ts=data.get(ATTR_THREAD_TS),
                username=data[ATTR_FILE].get(ATTR_USERNAME),
                password=data[ATTR_FILE].get(ATTR_PASSWORD),
            )

        # Message Type 3: A message that uploads a local file
        return await self._async_send_local_file_message(
            data[ATTR_FILE][ATTR_PATH],
            targets,
            message,
            title,
            thread_ts=data.get(ATTR_THREAD_TS),
        )

    async def _async_get_channel_id(self, channel_name: str) -> str | None:
        """Get the Slack channel ID from the channel name.

        This method retrieves the channel ID for a given Slack channel name by
        querying the Slack API. It handles both public and private channels.
        Including this so users can  provide channel names instead of IDs.

        Args:
            channel_name (str): The name of the Slack channel.

        Returns:
            str | None: The ID of the Slack channel if found, otherwise None.

        Raises:
            SlackApiError: If there is an error while communicating with the Slack API.

        """
        try:
            # Remove # if present
            channel_name = channel_name.lstrip("#")

            # Get channel list
            # Multiple types is not working. Tested here: https://api.slack.com/methods/conversations.list/test
            # response = await self._client.conversations_list(types="public_channel,private_channel")
            #
            # Workaround for the types parameter not working
            channels = []
            for channel_type in ("public_channel", "private_channel"):
                response = await self._client.conversations_list(types=channel_type)
                channels.extend(response["channels"])

            # Find channel ID
            for channel in channels:
                if channel["name"] == channel_name:
                    return cast(str, channel["id"])

            _LOGGER.error("Channel %s not found", channel_name)

        except SlackApiError as err:
            _LOGGER.error("Error getting channel ID: %r", err)

        return None
