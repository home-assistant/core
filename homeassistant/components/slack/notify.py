"""Slack platform for notify component."""

from __future__ import annotations

import asyncio
from io import BytesIO
import logging
import os
from time import time
from typing import Any, TypedDict, cast
from urllib.parse import urlparse

import aiofiles
from aiohttp import BasicAuth
from aiohttp.client_exceptions import ClientError
from PIL import Image
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
        """Asynchronously sends a remote file message to a Slack channel.

        This method performs the following steps:
        1. Checks if the provided URL is allowed.
        2. Converts channel names to IDs.
        3. Downloads the image from the provided URL.
        4. Resizes the image to meet minimum dimension requirements.
        5. Uploads the image to Slack.
        6. Shares the uploaded file in the specified Slack channel.

        Args:
            url (str): The URL of the remote file to be sent.
            targets (list[str]): List of target Slack channels.
            message (str): The message to accompany the file.
            title (str | None): The title of the file.
            thread_ts (str | None): The thread timestamp to reply to.
            username (str | None, optional): Username for basic authentication. Defaults to None.
            password (str | None, optional): Password for basic authentication. Defaults to None.

        Returns:
            None

        Raises:
            SlackApiError: If there is an error with the Slack API request.
            ClientError: If there is a client-side error

        """
        # Step 1: Check preconditions
        # Check if the URL is allowed
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

        # Step 2: Download the image
        session = aiohttp_client.async_get_clientsession(self._hass)

        kwargs: AuthDictT = {}
        if username and password is not None:
            kwargs = {"auth": BasicAuth(username, password=password)}

        image_data = None
        try:
            resp = await session.request("get", url, **kwargs)
            resp.raise_for_status()
            image_data = await resp.read()  # Read image data on success
        except ClientError as err:
            _LOGGER.error("Error while retrieving %s: %r", url, err)
            return

        # Step 3: Resize the image to meet the minimum dimension requirements
        # https://api.slack.com/methods/files.remote.add#markdown
        if not image_data:
            _LOGGER.error("Image data could not be retrieved")
            return

        include_preview = True
        try:
            # Open the image and convert to RGB if necessary
            image = Image.open(BytesIO(image_data))
            if image.mode in ("RGBA", "P"):  # Convert if image has alpha channel
                image = image.convert("RGB")

            # Get current dimensions
            width, height = image.size

            # Determine the scaling factor to meet minimum dimensions
            scale_w = 800 / width if width < 800 else 1
            scale_h = 400 / height if height < 400 else 1
            scale = max(scale_w, scale_h)  # Scale up to meet both requirements

            # Resize if necessary
            if scale > 1:
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = image.resize((new_width, new_height), Image.LANCZOS)
                _LOGGER.info("Image resized to %sx%s", new_width, new_height)
            else:
                _LOGGER.info(
                    "Image meets the minimum dimension requirements; no resizing needed"
                )

            # Save the image to a bytes buffer
            image_buffer = BytesIO()
            image.save(image_buffer, format="PNG")
            image_buffer.seek(0)
        except OSError:
            # If the file is not an image, handle it as a generic file
            image_buffer = BytesIO(image_data)
            include_preview = False
        except ValueError as e:
            _LOGGER.error("Error processing image: %s", e)
            return

        # Step 4: Upload the image to Slack
        add_response = None
        try:
            if include_preview:
                add_response = await self._client.files_remote_add(
                    external_id=f"ha_{int(time())}",  # Unique identifier
                    external_url=url,
                    title=title or os.path.basename(url),
                    preview_image=image_buffer,  # will be displayed in channels
                )
            else:
                add_response = await self._client.files_remote_add(
                    external_id=f"ha_{int(time())}",  # Unique identifier
                    external_url=url,
                    title=title or os.path.basename(url),
                )
            # Log the response for debugging
            _LOGGER.debug("Remote add response: %s", add_response)

            metadata = add_response.get("file")
            if metadata is not None:
                _LOGGER.info("File uploaded: %s", metadata.get("permalink"))
            else:
                _LOGGER.error("Metadata is missing in the Slack response")
        except (SlackApiError, ClientError) as err:
            _LOGGER.error("Error uploading file: %s", err)

        # Step 5: Share the file in the channel
        if add_response and add_response.get("file"):
            external_id = add_response["file"]["id"]
            tasks = {
                channel_id: self._client.files_remote_share(
                    file=external_id,
                    title=title or os.path.basename(url),
                    channels=channel_id,
                    initial_comment=message,
                    text=message,
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
        else:
            _LOGGER.error("Error while sharing remote file: %r", add_response)

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
