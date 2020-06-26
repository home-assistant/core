"""Slack platform for notify component."""
import asyncio
import logging
import os
from urllib.parse import urlparse

from aiohttp import BasicAuth
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
ATTR_USERNAME = "username"

CONF_DEFAULT_CHANNEL = "default_channel"

DEFAULT_TIMEOUT_SECONDS = 15

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


async def _async_get_remote_file_contents(hass, url, *, username=None, password=None):
    """Get the binary contents of a remote file."""
    session = aiohttp_client.async_get_clientsession(hass)

    if username and password:
        resp = session.request("get", url, auth=BasicAuth(username, password=password))
    else:
        resp = session.request("get", url)

    async with resp:
        resp.raise_for_status()
        return await resp.read()


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
        """Upload a remote file (with message) to Slack."""
        try:
            file_as_bytes = await _async_get_remote_file_contents(
                self._hass, url, username=username, password=password
            )
        except ClientError as err:
            _LOGGER.error("Error while retrieving %s: %s", url, err)
            return

        filename = _async_get_filename_from_url(url)

        try:
            await self._client.files_upload(
                channels=",".join(targets),
                file=file_as_bytes,
                filename=filename,
                initial_comment=message,
                title=title or filename,
            )
        except SlackApiError as err:
            _LOGGER.error("Error while uploading file-based message: %s", err)

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
        data = kwargs[ATTR_DATA] or {}
        title = kwargs.get(ATTR_TITLE)
        targets = _async_sanitize_channel_names(
            kwargs.get(ATTR_TARGET, [self._default_channel])
        )

        if ATTR_FILE in data:
            if not self.hass.config.is_allowed_path(data[ATTR_FILE]):
                _LOGGER.error(
                    "Filepath does not exist or is not allowed: %s", data[ATTR_FILE]
                )
                return

            if data[ATTR_FILE].startswith(("http://", "https://")):
                return await self._async_send_remote_file_message(
                    data[ATTR_FILE],
                    targets,
                    message,
                    title,
                    username=data.get(ATTR_USERNAME),
                    password=data.get(ATTR_PASSWORD),
                )

            return await self._async_send_local_file_message(
                data[ATTR_FILE], targets, message, title
            )

        attachments = data.get(ATTR_ATTACHMENTS, {})
        if attachments:
            _LOGGER.warning(
                "Attachments are deprecated and part of Slack's legacy API; support "
                "for them will be dropped in 0.114.0. In most cases, Blocks should be "
                "used instead: https://www.home-assistant.io/integrations/slack/"
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
