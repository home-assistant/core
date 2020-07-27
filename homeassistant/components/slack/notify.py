"""Slack platform for notify component."""
import asyncio
import logging
import os
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

_LOGGER = logging.getLogger(__name__)

ATTR_ATTACHMENTS = "attachments"
ATTR_BLOCKS = "blocks"
ATTR_BLOCKS_TEMPLATE = "blocks_template"
ATTR_FILE = "file"
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
        vol.Optional(ATTR_ATTACHMENTS): list,
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


async def async_get_service(hass, config, discovery_info=None):
    """Set up the Slack notification service."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = WebClient(token=config[CONF_API_KEY], run_async=True, session=session)

    try:
        await client.auth_test()
    except SlackApiError as err:
        _LOGGER.error("Error while setting up integration: %s", err)
        return

    return SlackNotificationService(
        hass,
        client,
        config[CONF_DEFAULT_CHANNEL],
        username=config.get(CONF_USERNAME),
        icon=config.get(CONF_ICON),
    )


@callback
def _async_get_filename_from_url(url):
    """Return the filename of a passed URL."""
    parsed_url = urlparse(url)
    return os.path.basename(parsed_url.path)


@callback
def _async_sanitize_channel_names(channel_list):
    """Remove any # symbols from a channel list."""
    return [channel.lstrip("#") for channel in channel_list]


@callback
def _async_templatize_blocks(hass, value):
    """Recursive template creator helper function."""
    if isinstance(value, list):
        return [_async_templatize_blocks(hass, item) for item in value]
    if isinstance(value, dict):
        return {
            key: _async_templatize_blocks(hass, item) for key, item in value.items()
        }

    tmpl = template.Template(value, hass=hass)
    return tmpl.async_render()


class SlackNotificationService(BaseNotificationService):
    """Define the Slack notification logic."""

    def __init__(self, hass, client, default_channel, username, icon):
        """Initialize."""
        self._client = client
        self._default_channel = default_channel
        self._hass = hass
        self._icon = icon
        self._username = username

    async def _async_send_local_file_message(self, path, targets, message, title):
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
        except SlackApiError as err:
            _LOGGER.error("Error while uploading file-based message: %s", err)

    async def _async_send_remote_file_message(
        self, url, targets, message, title, *, username=None, password=None
    ):
        """Upload a remote file (with message) to Slack.

        Note that we bypass the python-slackclient WebClient and use aiohttp directly,
        as the former would require us to download the entire remote file into memory
        first before uploading it to Slack.
        """
        if not self._hass.config.is_allowed_external_url(url):
            _LOGGER.error("URL is not allowed: %s", url)
            return

        filename = _async_get_filename_from_url(url)
        session = aiohttp_client.async_get_clientsession(self.hass)

        kwargs = {}
        if username and password is not None:
            kwargs = {"auth": BasicAuth(username, password=password)}

        resp = await session.request("get", url, **kwargs)

        try:
            resp.raise_for_status()
        except ClientError as err:
            _LOGGER.error("Error while retrieving %s: %s", url, err)
            return

        data = FormData(
            {
                "channels": ",".join(targets),
                "filename": filename,
                "initial_comment": message,
                "title": title or filename,
                "token": self._client.token,
            },
            charset="utf-8",
        )
        data.add_field("file", resp.content, filename=filename)

        try:
            await session.post("https://slack.com/api/files.upload", data=data)
        except ClientError as err:
            _LOGGER.error("Error while uploading file message: %s", err)

    async def _async_send_text_only_message(
        self, targets, message, title, attachments, blocks
    ):
        """Send a text-only message."""
        tasks = {
            target: self._client.chat_postMessage(
                channel=target,
                text=message,
                attachments=attachments,
                blocks=blocks,
                icon_emoji=self._icon,
                link_names=True,
                username=self._username,
            )
            for target in targets
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for target, result in zip(tasks, results):
            if isinstance(result, SlackApiError):
                _LOGGER.error(
                    "There was a Slack API error while sending to %s: %s",
                    target,
                    result,
                )

    async def async_send_message(self, message, **kwargs):
        """Send a message to Slack."""
        data = kwargs.get(ATTR_DATA)

        if data is None:
            data = {}

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
            attachments = data.get(ATTR_ATTACHMENTS, {})
            if attachments:
                _LOGGER.warning(
                    "Attachments are deprecated and part of Slack's legacy API; "
                    "support for them will be dropped in 0.114.0. In most cases, "
                    "Blocks should be used instead: "
                    "https://www.home-assistant.io/integrations/slack/"
                )

            if ATTR_BLOCKS_TEMPLATE in data:
                blocks = _async_templatize_blocks(self.hass, data[ATTR_BLOCKS_TEMPLATE])
            elif ATTR_BLOCKS in data:
                blocks = data[ATTR_BLOCKS]
            else:
                blocks = {}

            return await self._async_send_text_only_message(
                targets, message, title, attachments, blocks
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
