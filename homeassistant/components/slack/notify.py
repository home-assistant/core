"""Slack platform for notify component."""
import asyncio
import logging
import os
from urllib.parse import urlparse

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

_LOGGER = logging.getLogger(__name__)

ATTR_ATTACHMENTS = "attachments"
ATTR_BLOCKS = "blocks"
ATTR_FILE = "file"

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
def _async_sanitize_channel_names(channel_list):
    """Remove any # symbols from a channel list."""
    return [channel.lstrip("#") for channel in channel_list]


class SlackNotificationService(BaseNotificationService):
    """Define the Slack notification logic."""

    def __init__(self, hass, client, default_channel, username, icon):
        """Initialize."""
        self._client = client
        self._default_channel = default_channel
        self._hass = hass
        self._icon = icon

        if username or self._icon:
            self._as_user = False
        else:
            self._as_user = True

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

    async def _async_send_text_only_message(
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
        blocks = data.get(ATTR_BLOCKS, {})

        return await self._async_send_text_only_message(
            targets, message, title, attachments, blocks
        )
