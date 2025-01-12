"""Slack platform for notify component."""

from __future__ import annotations

import asyncio
import logging
import os
from time import time
from typing import Any, TypedDict, cast
from urllib.parse import urlparse

import aiofiles
from aiohttp import BasicAuth
from aiohttp.client_exceptions import ClientError
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncSlackResponse, AsyncWebClient
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
        """Share an external file with a message to Slack.

        This function uploads a file via `files.remote.add` and shares it with the specified Slack channels.

        Args:
            url (str): The external URL of the file to share.
            targets (list[str]): List of Slack channel IDs to share the file with.
            message (str): The message to accompany the file.
            title (str | None): Title for the file.
            thread_ts (str | None): Thread timestamp to reply within a Slack thread.
            username (str | None, optional): Username for basic authentication for the URL. Defaults to None.
            password (str | None, optional): Password for basic authentication for the URL. Defaults to None.

        Returns:
            None

        Raises:
            SlackApiError: If there is an error with the Slack API request.
            ClientError: If there is a client-side error.

        """
        if not self._hass.config.is_allowed_external_url(url):
            _LOGGER.error("URL is not allowed: %s", url)
            return

        # Convert channel names to IDs
        channel_ids = []
        for target_channel in targets:
            channel_id = await self._async_get_channel_id(target_channel)
            if channel_id:
                channel_ids.append(channel_id)

        if not channel_ids:
            _LOGGER.error("No valid channels found")
            return

        session = aiohttp_client.async_get_clientsession(self._hass)

        kwargs: AuthDictT = {}
        if username and password is not None:
            kwargs = {"auth": BasicAuth(username, password=password)}

        try:
            resp = await session.request("get", url, **kwargs)
            resp.raise_for_status()
        except ClientError as err:
            _LOGGER.error("Error while retrieving %s: %r", url, err)
            return

        filename = _async_get_filename_from_url(url)
        external_id = f"ha_{int(time())}"  # Unique identifier for the file
        form_data = {
            "external_id": external_id,
            "external_url": url,
            "title": title or filename,
            "initial_comment": message,
        }

        try:
            # Step 1: Add the file to Slack
            add_response = await self._client.files_remote_add(**form_data)
            if not add_response.get("ok", False):
                _LOGGER.error("Failed to add file to Slack: %s", add_response)
                return

            file_id = add_response["file"]["id"]

            # Step 2: Share the file in the specified channels
            for channel_id in channel_ids:
                try:
                    share_response = await self._client.files_remote_share(
                        file=file_id,
                        channels=channel_id,
                        initial_comment=message,
                    )
                    if not share_response.get("ok", False):
                        _LOGGER.error(
                            "Failed to share file in channel %s: %s",
                            channel_id,
                            share_response,
                        )
                except SlackApiError as err:
                    _LOGGER.error(
                        "Slack API error while sharing file in channel %s: %s",
                        channel_id,
                        err,
                    )

        except SlackApiError as err:
            _LOGGER.error("Slack API error while uploading file: %s", err)
        except ClientError as err:
            _LOGGER.error("Client error while uploading file: %r", err)

    async def _async_send_local_file_message(
        self,
        path: str,
        targets: list[str],
        message: str,
        title: str | None,
        thread_ts: str | None,
    ) -> None:
        """Upload a local file (with message) to Slack.

        Args:
            path (str): The local file path to upload.
            targets (list): The target Slack channel or user to send the file to.
            message (str): The message to accompany the file upload.
            title (str | None): The title of the file in Slack. Defaults to the file name if None.
            thread_ts (str | None): The thread timestamp to reply to. If None, the message is not a reply.

        Returns:
            None

        Raises:
            SlackApiError: If there is an error with the Slack API request.
            ClientError: If there is a client-side error.

        """
        if not self._hass.config.is_allowed_path(path):
            _LOGGER.error("Path does not exist or is not allowed: %s", path)
            return

        if not os.path.exists(path):
            _LOGGER.error("File does not exist: %s", path)
            return

        # Convert channel names to IDs
        channel_ids = []
        for target_channel in targets:
            channel_id = await self._async_get_channel_id(target_channel)
            if channel_id:
                channel_ids.append(channel_id)

        if not channel_ids:
            _LOGGER.error("No valid channels found")
            return

        try:
            async with aiofiles.open(path, "rb") as file:
                file_content = await file.read()

            tasks = {
                channel_id: self._client.files_upload_v2(
                    file=file_content,
                    filename=os.path.basename(path),
                    title=title or os.path.basename(path),
                    channel=channel_id,
                    initial_comment=message,
                )
                for channel_id in channel_ids
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
                    _LOGGER.error(
                        "Error while sending message to %s: %r", target, result
                    )
                elif isinstance(result, AsyncSlackResponse):
                    metadata = result.get("file")
                    if metadata:
                        _LOGGER.info("File uploaded: %s", metadata.get("permalink"))
                    else:
                        _LOGGER.error("Error while sharing remote file: %r", result)

        except (SlackApiError, ClientError) as err:
            _LOGGER.error("Error while uploading file-based message: %r", err)

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
        """Asynchronously send a message to Slack.

        This method handles three types of messages:
        1. Text-only message
        2. Message that uploads a remote file
        3. Message that uploads a local file

        Args:
            message (str): The message to send.
            **kwargs (Any): Additional parameters for the message.

        Keyword Args:
            ATTR_DATA (dict): Additional data for the message.
            ATTR_TITLE (str): Title of the message.
            ATTR_TARGET (list): List of target channels.
            ATTR_FILE (dict): File information for file upload messages.
            ATTR_BLOCKS_TEMPLATE (str): Template for message blocks.
            ATTR_BLOCKS (list): List of message blocks.
            ATTR_USERNAME (str): Username to display.
            ATTR_ICON (str): Icon to display.
            ATTR_THREAD_TS (str): Thread timestamp for threading messages.
            ATTR_URL (str): URL of the remote file to upload.
            ATTR_PATH (str): Path of the local file to upload.
            ATTR_PASSWORD (str): Password for the remote file.

        Returns:
            None

        """

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
