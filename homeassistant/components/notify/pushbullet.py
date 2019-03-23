"""
Pushbullet platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushbullet/
"""
import logging
import mimetypes

import voluptuous as vol

from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv

from . import (
    ATTR_DATA, ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA,
    BaseNotificationService)

REQUIREMENTS = ['pushbullet.py==0.11.0']

_LOGGER = logging.getLogger(__name__)

ATTR_URL = 'url'
ATTR_FILE = 'file'
ATTR_FILE_URL = 'file_url'
ATTR_LIST = 'list'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Pushbullet notification service."""
    from pushbullet import PushBullet
    from pushbullet import InvalidKeyError

    try:
        pushbullet = PushBullet(config[CONF_API_KEY])
    except InvalidKeyError:
        _LOGGER.error("Wrong API key supplied")
        return None

    return PushBulletNotificationService(pushbullet)


class PushBulletNotificationService(BaseNotificationService):
    """Implement the notification service for Pushbullet."""

    def __init__(self, pb):
        """Initialize the service."""
        self.pushbullet = pb
        self.pbtargets = {}
        self.refresh()

    def refresh(self):
        """Refresh devices, contacts, etc.

        pbtargets stores all targets available from this Pushbullet instance
        into a dict. These are Pushbullet objects!. It sacrifices a bit of
        memory for faster processing at send_message.

        As of sept 2015, contacts were replaced by chats. This is not
        implemented in the module yet.
        """
        self.pushbullet.refresh()
        self.pbtargets = {
            'device': {
                tgt.nickname.lower(): tgt for tgt in self.pushbullet.devices},
            'channel': {
                tgt.channel_tag.lower(): tgt for
                tgt in self.pushbullet.channels},
        }

    def send_message(self, message=None, **kwargs):
        """Send a message to a specified target.

        If no target specified, a 'normal' push will be sent to all devices
        linked to the Pushbullet account.
        Email is special, these are assumed to always exist. We use a special
        call which doesn't require a push object.
        """
        targets = kwargs.get(ATTR_TARGET)
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA)
        refreshed = False

        if not targets:
            # Backward compatibility, notify all devices in own account.
            self._push_data(message, title, data, self.pushbullet)
            _LOGGER.info("Sent notification to self")
            return

        # Main loop, process all targets specified.
        for target in targets:
            try:
                ttype, tname = target.split('/', 1)
            except ValueError:
                _LOGGER.error("Invalid target syntax: %s", target)
                continue

            # Target is email, send directly, don't use a target object.
            # This also seems to work to send to all devices in own account.
            if ttype == 'email':
                self._push_data(message, title, data, self.pushbullet, tname)
                _LOGGER.info("Sent notification to email %s", tname)
                continue

            # Refresh if name not found. While awaiting periodic refresh
            # solution in component, poor mans refresh.
            if ttype not in self.pbtargets:
                _LOGGER.error("Invalid target syntax: %s", target)
                continue

            tname = tname.lower()

            if tname not in self.pbtargets[ttype] and not refreshed:
                self.refresh()
                refreshed = True

            # Attempt push_note on a dict value. Keys are types & target
            # name. Dict pbtargets has all *actual* targets.
            try:
                self._push_data(message, title, data,
                                self.pbtargets[ttype][tname])
                _LOGGER.info("Sent notification to %s/%s", ttype, tname)
            except KeyError:
                _LOGGER.error("No such target: %s/%s", ttype, tname)
                continue

    def _push_data(self, message, title, data, pusher, email=None):
        """Create the message content."""
        from pushbullet import PushError
        if data is None:
            data = {}
        data_list = data.get(ATTR_LIST)
        url = data.get(ATTR_URL)
        filepath = data.get(ATTR_FILE)
        file_url = data.get(ATTR_FILE_URL)
        try:
            email_kwargs = {}
            if email:
                email_kwargs['email'] = email
            if url:
                pusher.push_link(title, url, body=message, **email_kwargs)
            elif filepath:
                if not self.hass.config.is_allowed_path(filepath):
                    _LOGGER.error("Filepath is not valid or allowed")
                    return
                with open(filepath, 'rb') as fileh:
                    filedata = self.pushbullet.upload_file(fileh, filepath)
                    if filedata.get('file_type') == 'application/x-empty':
                        _LOGGER.error("Can not send an empty file")
                        return
                    filedata.update(email_kwargs)
                    pusher.push_file(title=title, body=message,
                                     **filedata)
            elif file_url:
                if not file_url.startswith('http'):
                    _LOGGER.error("URL should start with http or https")
                    return
                pusher.push_file(title=title, body=message,
                                 file_name=file_url, file_url=file_url,
                                 file_type=(mimetypes
                                            .guess_type(file_url)[0]),
                                 **email_kwargs)
            elif data_list:
                pusher.push_list(title, data_list, **email_kwargs)
            else:
                pusher.push_note(title, message, **email_kwargs)
        except PushError as err:
            _LOGGER.error("Notify failed: %s", err)
