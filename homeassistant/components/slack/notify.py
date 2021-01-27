"""Slack platform for notify component."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, List, Optional, TypedDict
from urllib.parse import urlparse

from aiohttp import BasicAuth, FormData
from aiohttp.client_exceptions import ClientError
from slack import WebClient
from slack.errors import SlackApiError
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY, CONF_ICON, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
import homeassistant.helpers.template as template
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

_LOGGER = logging.getLogger(__name__)

ATTR_BLOCKS = "blocks"
ATTR_BLOCKS_TEMPLATE = "blocks_template"
ATTR_FILE = "file"
ATTR_ICON = "icon"
ATTR_PASSWORD = "password"
ATTR_PATH = "path"
ATTR_URL = "url"
ATTR_USERNAME = "username"

CONF_DEFAULT_CHANNEL = "default_channel"

DEFAULT_TIMEOUT_SECONDS = 15

FILE_PATH_SCHEMA = vol.Schema({vol.Required(ATTR_PATH): cv.isfile})

FILE_URL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URL): cv.url,
        vol.Inclusive(ATTR_USERNAME, "credentials"): cv.string,
        vol.Inclusive(ATTR_PASSWORD, "credentials"): cv.string,
    }
)

DATA_FILE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_FILE): vol.Any(FILE_PATH_SCHEMA, FILE_URL_SCHEMA)}
)

DATA_TEXT_ONLY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_USERNAME): cv.string,
        vol.Optional(ATTR_ICON): cv.string,
        vol.Optional(ATTR_BLOCKS): list,
        vol.Optional(ATTR_BLOCKS_TEMPLATE): list,
    }
)

DATA_SCHEMA = vol.All(
    cv.ensure_list, [vol.Any(DATA_FILE_SCHEMA, DATA_TEXT_ONLY_SCHEMA)]
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DEFAULT_CHANNEL): cv.string,
        vol.Optional(CONF_ICON): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
    }
)


class AuthDictT(TypedDict, total=False):
    """Type for auth request data."""

    auth: BasicAuth


class FormDataT(TypedDict):
    """Type for form data, file upload."""

    channels: str
    filename: str
    initial_comment: str
    title: str
    token: str


class MessageT(TypedDict, total=False):
    """Type for message data."""

    link_names: bool
    text: str
    username: str  # Optional key
    icon_url: str  # Optional key
    icon_emoji: str  # Optional key
    blocks: List[Any]  # Optional key


async def async_get_service(
    hass: HomeAssistantType,
    config: ConfigType,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> Optional[SlackNotificationService]:
    """Set up the Slack notification service."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = WebClient(token=config[CONF_API_KEY], run_async=True, session=session)

    try:
        await client.auth_test()
    except SlackApiError as err:
        _LOGGER.error("Error while setting up integration: %r", err)
        return None
    except ClientError as err:
        _LOGGER.warning(
            "Error testing connection to slack: %r "
            "Continuing setup anyway, but notify service might not work",
            err,
        )

    return SlackNotificationService(
        hass,
        client,
        config[CONF_DEFAULT_CHANNEL],
        username=config.get(CONF_USERNAME),
        icon=config.get(CONF_ICON),
    )


@callback
def _async_get_filename_from_url(url: str) -> str:
    """Return the filename of a passed URL."""
    parsed_url = urlparse(url)
    return os.path.basename(parsed_url.path)


@callback
def _async_sanitize_channel_names(channel_list: List[str]) -> List[str]:
    """Remove any # symbols from a channel list."""
    return [channel.lstrip("#") for channel in channel_list]


@callback
def _async_templatize_blocks(hass: HomeAssistantType, value: Any) -> Any:
    """Recursive template creator helper function."""
    if isinstance(value, list):
        return [_async_templatize_blocks(hass, item) for item in value]
    if isinstance(value, dict):
        return {
            key: _async_templatize_blocks(hass, item) for key, item in value.items()
        }

    tmpl = template.Template(value, hass=hass)  # type: ignore  # no-untyped-call
    return tmpl.async_render(parse_result=False)


class SlackNotificationService(BaseNotificationService):
    """Define the Slack notification logic."""

    def __init__(
        self,
        hass: HomeAssistantType,
        client: WebClient,
        default_channel: str,
        username: Optional[str],
        icon: Optional[str],
    ) -> None:
        """Initialize."""
        self._client = client
        self._default_channel = default_channel
        self._hass = hass
        self._icon = icon
        self._username = username

    async def _async_send_local_file_message(
        self,
        path: str,
        targets: List[str],
        message: str,
        title: Optional[str],
    ) -> None:
        """Upload a local file (with message) to Slack."""
        if not self._hass.config.is_allowed_path(path):
            _LOGGER.error("Path does not exist or is not allowed: %s", path)
            return

        parsed_url = urlparse(path)
        filename = os.path.basename(parsed_url.path)

        try:
            await self._client.files_upload(
                channels=",".join(targets),
                file=path,
                filename=filename,
                initial_comment=message,
                title=title or filename,
            )
        except (SlackApiError, ClientError) as err:
            _LOGGER.error("Error while uploading file-based message: %r", err)

    async def _async_send_remote_file_message(
        self,
        url: str,
        targets: List[str],
        message: str,
        title: Optional[str],
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Upload a remote file (with message) to Slack.

        Note that we bypass the python-slackclient WebClient and use aiohttp directly,
        as the former would require us to download the entire remote file into memory
        first before uploading it to Slack.
        """
        if not self._hass.config.is_allowed_external_url(url):
            _LOGGER.error("URL is not allowed: %s", url)
            return

        filename = _async_get_filename_from_url(url)
        session = aiohttp_client.async_get_clientsession(self._hass)

        kwargs: AuthDictT = {}
        if username and password is not None:
            kwargs = {"auth": BasicAuth(username, password=password)}

        resp = await session.request("get", url, **kwargs)

        try:
            resp.raise_for_status()
        except ClientError as err:
            _LOGGER.error("Error while retrieving %s: %r", url, err)
            return

        form_data: FormDataT = {
            "channels": ",".join(targets),
            "filename": filename,
            "initial_comment": message,
            "title": title or filename,
            "token": self._client.token,
        }

        data = FormData(form_data, charset="utf-8")
        data.add_field("file", resp.content, filename=filename)

        try:
            await session.post("https://slack.com/api/files.upload", data=data)
        except ClientError as err:
            _LOGGER.error("Error while uploading file message: %r", err)

    async def _async_send_text_only_message(
        self,
        targets: List[str],
        message: str,
        title: Optional[str],
        *,
        username: Optional[str] = None,
        icon: Optional[str] = None,
        blocks: Optional[Any] = None,
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

        tasks = {
            target: self._client.chat_postMessage(**message_dict, channel=target)
            for target in targets
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for target, result in zip(tasks, results):
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
            kwargs.get(ATTR_TARGET, [self._default_channel])
        )

        # Message Type 1: A text-only message
        if ATTR_FILE not in data:
            if ATTR_BLOCKS_TEMPLATE in data:
                blocks = _async_templatize_blocks(
                    self._hass, data[ATTR_BLOCKS_TEMPLATE]
                )
            elif ATTR_BLOCKS in data:
                blocks = data[ATTR_BLOCKS]
            else:
                blocks = None

            return await self._async_send_text_only_message(
                targets,
                message,
                title,
                username=data.get(ATTR_USERNAME, self._username),
                icon=data.get(ATTR_ICON, self._icon),
                blocks=blocks,
            )

        # Message Type 2: A message that uploads a remote file
        if ATTR_URL in data[ATTR_FILE]:
            return await self._async_send_remote_file_message(
                data[ATTR_FILE][ATTR_URL],
                targets,
                message,
                title,
                username=data[ATTR_FILE].get(ATTR_USERNAME),
                password=data[ATTR_FILE].get(ATTR_PASSWORD),
            )

        # Message Type 3: A message that uploads a local file
        return await self._async_send_local_file_message(
            data[ATTR_FILE][ATTR_PATH], targets, message, title
        )
