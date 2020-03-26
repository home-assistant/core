"""Slack platform for notify component."""
import asyncio
import logging
import os
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import RequestException
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
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ICON,
    CONF_USERNAME,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_ATTACHMENTS = "attachments"
ATTR_AUTH_TYPE = "auth"
ATTR_BLOCKS = "blocks"
ATTR_FILE = "file"
ATTR_FILE_URL = "url"
ATTR_FILE_PATH = "path"
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
        session,
        config[CONF_DEFAULT_CHANNEL],
        username=config.get(CONF_USERNAME),
        icon=config.get(CONF_ICON),
    )


def _get_remote_file_contents(url, username=None, password=None, auth_type=None):
    """Retrieve a remote file via URL and return its binary content."""
    if auth_type == HTTP_BASIC_AUTHENTICATION:
        resp = requests.get(
            url,
            auth=HTTPBasicAuth(username, password),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    elif auth_type == HTTP_DIGEST_AUTHENTICATION:
        resp = requests.get(
            url,
            auth=HTTPDigestAuth(username, password),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    else:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)

    resp.raise_for_status()
    return resp.content


@callback
def _async_get_filename_from_url(url):
    """Return the filename of a passed URL."""
    parsed_url = urlparse(url)
    return os.path.basename(parsed_url.path)


@callback
def _async_sanitize_channel_names(channel_list):
    """Remove any # symbols from a channel list."""
    return [channel.replace("#", "") for channel in channel_list]


class SlackNotificationService(BaseNotificationService):
    """Define the Slack notification logic."""

    def __init__(self, hass, client, session, default_channel, username, icon):
        """Initialize."""
        self._client = client
        self._default_channel = default_channel
        self._hass = hass
        self._icon = icon
        self._session = session
        self._username = username

        if self._username or self._icon:
            self._as_user = False
        else:
            self._as_user = True

    async def _async_send_local_file_message(self, path, targets, message, title):
        """Upload a local file (with message) to Slack."""
        if not self._hass.config.is_allowed_path(path):
            _LOGGER.error("Path does not exist or is not allowed: %s", path)
            return

        filename = _async_get_filename_from_url(path)

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

    async def _async_send_regular_message(
        self, targets, message, title, attachments, blocks
    ):
        """Send a text-only message."""
        tasks = {
            target: self._client.chat_postMessage(
                channel=target,
                text=message,
                as_user=self._as_user,
                attachments=attachments,
                blocks=blocks,
                icon_emoji=self._icon,
                link_names=True,
            )
            for target in targets
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for target, result in zip(tasks, results):
            if isinstance(result, SlackApiError):
                _LOGGER.error(
                    "There was a Slack API error while sending a message to %s: %s",
                    target,
                    result,
                )

    async def _async_send_remote_file_message(
        self, url, targets, message, title, username, password, auth_type
    ):
        """Upload a remote file (with message) to Slack."""
        try:
            file_as_bytes = await self._hass.async_add_executor_job(
                _get_remote_file_contents, url, username, password, auth_type
            )
        except RequestException as err:
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

    async def async_send_message(self, message, **kwargs):
        """Send a message to Slack."""
        data = kwargs[ATTR_DATA] or {}
        title = kwargs.get(ATTR_TITLE)
        targets = _async_sanitize_channel_names(
            kwargs.get(ATTR_TARGET, [self._default_channel])
        )

        if ATTR_FILE not in data:
            attachments = data.get(ATTR_ATTACHMENTS, {})
            if attachments:
                _LOGGER.warning(
                    "Attachments are now part of Slack's legacy API; "
                    "in most cases, Blocks should be used instead: "
                    "https://www.home-assistant.io/integrations/slack/"
                )
            blocks = data.get(ATTR_BLOCKS, {})

            return await self._async_send_regular_message(
                targets, message, title, attachments, blocks
            )

        file_data = data[ATTR_FILE]

        if ATTR_FILE_PATH not in file_data and ATTR_FILE_URL not in file_data:
            _LOGGER.error('A file path/URL must be provided when using the "file" key')
            return

        if ATTR_FILE_PATH in file_data:
            return await self._async_send_local_file_message(
                file_data[ATTR_FILE_PATH], targets, message, title
            )

        return await self._async_send_remote_file_message(
            file_data[ATTR_FILE_URL],
            targets,
            message,
            title,
            data.get(ATTR_USERNAME),
            data.get(ATTR_PASSWORD),
            data.get(ATTR_AUTH_TYPE),
        )
