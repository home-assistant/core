"""Pushbullet platform for notify component."""

from __future__ import annotations

import logging
import mimetypes
from typing import TYPE_CHECKING, Any

from pushbullet import PushBullet, PushError
from pushbullet.channel import Channel
from pushbullet.device import Device
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .api import PushBulletNotificationProvider
from .const import ATTR_FILE, ATTR_FILE_URL, ATTR_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> PushBulletNotificationService | None:
    """Get the Pushbullet notification service."""
    if TYPE_CHECKING:
        assert discovery_info is not None
    pb_provider: PushBulletNotificationProvider = hass.data[DOMAIN][
        discovery_info["entry_id"]
    ]
    return PushBulletNotificationService(hass, pb_provider.pushbullet)


class PushBulletNotificationService(BaseNotificationService):
    """Implement the notification service for Pushbullet."""

    def __init__(self, hass: HomeAssistant, pushbullet: PushBullet) -> None:
        """Initialize the service."""
        self.hass = hass
        self.pushbullet = pushbullet

    @property
    def pbtargets(self) -> dict[str, dict[str, Device | Channel]]:
        """Return device and channel detected targets."""
        return {
            "device": {tgt.nickname.lower(): tgt for tgt in self.pushbullet.devices},
            "channel": {
                tgt.channel_tag.lower(): tgt for tgt in self.pushbullet.channels
            },
        }

    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a specified target.

        If no target specified, a 'normal' push will be sent to all devices
        linked to the Pushbullet account.
        Email is special, these are assumed to always exist. We use a special
        call which doesn't require a push object.
        """
        targets: list[str] = kwargs.get(ATTR_TARGET, [])
        title: str = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data: dict[str, Any] = kwargs[ATTR_DATA] or {}

        if not targets:
            # Backward compatibility, notify all devices in own account.
            self._push_data(message, title, data, self.pushbullet)
            _LOGGER.debug("Sent notification to self")
            return

        # refresh device and channel targets
        self.pushbullet.refresh()

        # Main loop, process all targets specified.
        for target in targets:
            try:
                ttype, tname = target.split("/", 1)
            except ValueError as err:
                raise ValueError(f"Invalid target syntax: '{target}'") from err

            # Target is email, send directly, don't use a target object.
            # This also seems to work to send to all devices in own account.
            if ttype == "email":
                self._push_data(message, title, data, self.pushbullet, email=tname)
                _LOGGER.info("Sent notification to email %s", tname)
                continue

            # Target is sms, send directly, don't use a target object.
            if ttype == "sms":
                self._push_data(
                    message, title, data, self.pushbullet, phonenumber=tname
                )
                _LOGGER.info("Sent sms notification to %s", tname)
                continue

            if ttype not in self.pbtargets:
                raise ValueError(f"Invalid target syntax: {target}")

            tname = tname.lower()

            if tname not in self.pbtargets[ttype]:
                raise ValueError(f"Target: {target} doesn't exist")

            # Attempt push_note on a dict value. Keys are types & target
            # name. Dict pbtargets has all *actual* targets.
            self._push_data(message, title, data, self.pbtargets[ttype][tname])
            _LOGGER.debug("Sent notification to %s/%s", ttype, tname)

    def _push_data(
        self,
        message: str,
        title: str,
        data: dict[str, Any],
        pusher: PushBullet,
        email: str | None = None,
        phonenumber: str | None = None,
    ) -> None:
        """Create the message content."""
        kwargs = {"body": message, "title": title}
        if email:
            kwargs["email"] = email

        try:
            if phonenumber and pusher.devices:
                pusher.push_sms(pusher.devices[0], phonenumber, message)
                return
            if url := data.get(ATTR_URL):
                pusher.push_link(url=url, **kwargs)
                return
            if filepath := data.get(ATTR_FILE):
                if not self.hass.config.is_allowed_path(filepath):
                    raise ValueError("Filepath is not valid or allowed")
                with open(filepath, "rb") as fileh:
                    filedata = self.pushbullet.upload_file(fileh, filepath)
                if filedata.get("file_type") == "application/x-empty":
                    raise ValueError("Cannot send an empty file")
                kwargs.update(filedata)
                pusher.push_file(**kwargs)
            elif (file_url := data.get(ATTR_FILE_URL)) and vol.Url(file_url):
                pusher.push_file(
                    file_name=file_url,
                    file_url=file_url,
                    file_type=(mimetypes.guess_type(file_url)[0]),
                    **kwargs,
                )
            else:
                pusher.push_note(**kwargs)
        except PushError as err:
            raise HomeAssistantError(f"Notify failed: {err}") from err
