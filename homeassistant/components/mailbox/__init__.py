"""Support for Voice mailboxes."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any, Final

from aiohttp import web
from aiohttp.web_exceptions import HTTPNotFound

from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView
from homeassistant.config import config_per_platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_prepare_setup_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "mailbox"

EVENT: Final = "mailbox_updated"
CONTENT_TYPE_MPEG: Final = "audio/mpeg"
CONTENT_TYPE_NONE: Final = "none"

SCAN_INTERVAL = timedelta(seconds=30)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for mailboxes."""
    mailboxes: list[Mailbox] = []
    frontend.async_register_built_in_panel(hass, "mailbox", "mailbox", "mdi:mailbox")
    hass.http.register_view(MailboxPlatformsView(mailboxes))
    hass.http.register_view(MailboxMessageView(mailboxes))
    hass.http.register_view(MailboxMediaView(mailboxes))
    hass.http.register_view(MailboxDeleteView(mailboxes))

    async def async_setup_platform(
        p_type: str,
        p_config: ConfigType | None = None,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up a mailbox platform."""
        if p_config is None:
            p_config = {}
        if discovery_info is None:
            discovery_info = {}

        platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)

        if platform is None:
            _LOGGER.error("Unknown mailbox platform specified")
            return

        _LOGGER.info("Setting up %s.%s", DOMAIN, p_type)
        mailbox = None
        try:
            if hasattr(platform, "async_get_handler"):
                mailbox = await platform.async_get_handler(
                    hass, p_config, discovery_info
                )
            elif hasattr(platform, "get_handler"):
                mailbox = await hass.async_add_executor_job(
                    platform.get_handler, hass, p_config, discovery_info
                )
            else:
                raise HomeAssistantError("Invalid mailbox platform.")

            if mailbox is None:
                _LOGGER.error("Failed to initialize mailbox platform %s", p_type)
                return

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error setting up platform %s", p_type)
            return

        mailboxes.append(mailbox)
        mailbox_entity = MailboxEntity(mailbox)
        component = EntityComponent[MailboxEntity](
            logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL
        )
        component.register_shutdown()
        await component.async_add_entities([mailbox_entity])

    setup_tasks = [
        asyncio.create_task(async_setup_platform(p_type, p_config))
        for p_type, p_config in config_per_platform(config, DOMAIN)
        if p_type is not None
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    async def async_platform_discovered(
        platform: str, info: DiscoveryInfoType | None
    ) -> None:
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True


class MailboxEntity(Entity):
    """Entity for each mailbox platform to provide a badge display."""

    def __init__(self, mailbox: Mailbox) -> None:
        """Initialize mailbox entity."""
        self.mailbox = mailbox
        self.message_count = 0

    async def async_added_to_hass(self) -> None:
        """Complete entity initialization."""

        @callback
        def _mailbox_updated(event: Event) -> None:
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen(EVENT, _mailbox_updated)
        self.async_schedule_update_ha_state(True)

    @property
    def state(self) -> str:
        """Return the state of the binary sensor."""
        return str(self.message_count)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.mailbox.name

    async def async_update(self) -> None:
        """Retrieve messages from platform."""
        messages = await self.mailbox.async_get_messages()
        self.message_count = len(messages)


class Mailbox:
    """Represent a mailbox device."""

    def __init__(self, hass: HomeAssistant, name: str) -> None:
        """Initialize mailbox object."""
        self.hass = hass
        self.name = name

    @callback
    def async_update(self) -> None:
        """Send event notification of updated mailbox."""
        self.hass.bus.async_fire(EVENT)

    @property
    def media_type(self) -> str:
        """Return the supported media type."""
        raise NotImplementedError()

    @property
    def can_delete(self) -> bool:
        """Return if messages can be deleted."""
        return False

    @property
    def has_media(self) -> bool:
        """Return if messages have attached media files."""
        return False

    async def async_get_media(self, msgid: str) -> bytes:
        """Return the media blob for the msgid."""
        raise NotImplementedError()

    async def async_get_messages(self) -> list[dict[str, Any]]:
        """Return a list of the current messages."""
        raise NotImplementedError()

    async def async_delete(self, msgid: str) -> bool:
        """Delete the specified messages."""
        raise NotImplementedError()


class StreamError(Exception):
    """Media streaming exception."""


class MailboxView(HomeAssistantView):
    """Base mailbox view."""

    def __init__(self, mailboxes: list[Mailbox]) -> None:
        """Initialize a basic mailbox view."""
        self.mailboxes = mailboxes

    def get_mailbox(self, platform: str) -> Mailbox:
        """Retrieve the specified mailbox."""
        for mailbox in self.mailboxes:
            if mailbox.name == platform:
                return mailbox
        raise HTTPNotFound


class MailboxPlatformsView(MailboxView):
    """View to return the list of mailbox platforms."""

    url = "/api/mailbox/platforms"
    name = "api:mailbox:platforms"

    async def get(self, request: web.Request) -> web.Response:
        """Retrieve list of platforms."""
        platforms: list[dict[str, Any]] = []
        for mailbox in self.mailboxes:
            platforms.append(
                {
                    "name": mailbox.name,
                    "has_media": mailbox.has_media,
                    "can_delete": mailbox.can_delete,
                }
            )
        return self.json(platforms)


class MailboxMessageView(MailboxView):
    """View to return the list of messages."""

    url = "/api/mailbox/messages/{platform}"
    name = "api:mailbox:messages"

    async def get(self, request: web.Request, platform: str) -> web.Response:
        """Retrieve messages."""
        mailbox = self.get_mailbox(platform)
        messages = await mailbox.async_get_messages()
        return self.json(messages)


class MailboxDeleteView(MailboxView):
    """View to delete selected messages."""

    url = "/api/mailbox/delete/{platform}/{msgid}"
    name = "api:mailbox:delete"

    async def delete(self, request: web.Request, platform: str, msgid: str) -> None:
        """Delete items."""
        mailbox = self.get_mailbox(platform)
        await mailbox.async_delete(msgid)


class MailboxMediaView(MailboxView):
    """View to return a media file."""

    url = r"/api/mailbox/media/{platform}/{msgid}"
    name = "api:asteriskmbox:media"

    async def get(
        self, request: web.Request, platform: str, msgid: str
    ) -> web.Response:
        """Retrieve media."""
        mailbox = self.get_mailbox(platform)

        with suppress(asyncio.CancelledError, TimeoutError):
            async with asyncio.timeout(10):
                try:
                    stream = await mailbox.async_get_media(msgid)
                except StreamError as err:
                    _LOGGER.error("Error getting media: %s", err)
                    return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)
            if stream:
                return web.Response(body=stream, content_type=mailbox.media_type)

        return web.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)
