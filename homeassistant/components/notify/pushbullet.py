"""
PushBullet platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushbullet/
"""
import logging

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pushbullet.py==0.10.0']


# pylint: disable=unused-argument
def get_service(hass, config):
    """Get the PushBullet notification service."""
    from pushbullet import PushBullet
    from pushbullet import InvalidKeyError

    if CONF_API_KEY not in config:
        _LOGGER.error("Unable to find config key '%s'", CONF_API_KEY)
        return None

    try:
        pushbullet = PushBullet(config[CONF_API_KEY])
    except InvalidKeyError:
        _LOGGER.error(
            "Wrong API key supplied. "
            "Get it at https://www.pushbullet.com/account")
        return None

    return PushBulletNotificationService(pushbullet)


# pylint: disable=too-few-public-methods
class PushBulletNotificationService(BaseNotificationService):
    """Implement the notification service for Pushbullet."""

    def __init__(self, pb):
        """Initialize the service."""
        self.pushbullet = pb
        self.pbtargets = {}
        self.refresh()

    def refresh(self):
        """Refresh devices, contacts, etc.

        pbtargets stores all targets available from this pushbullet instance
        into a dict. These are PB objects!. It sacrifices a bit of memory
        for faster processing at send_message.

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
        linked to the PB account.
        Email is special, these are assumed to always exist. We use a special
        call which doesn't require a push object.
        """
        targets = kwargs.get(ATTR_TARGET)
        title = kwargs.get(ATTR_TITLE)
        refreshed = False

        if not targets:
            # Backward compatebility, notify all devices in own account
            self.pushbullet.push_note(title, message)
            _LOGGER.info('Sent notification to self')
            return

        # Make list if not so
        if not isinstance(targets, list):
            targets = [targets]

        # Main loop, Process all targets specified
        for target in targets:
            try:
                ttype, tname = target.split('/', 1)
            except ValueError:
                _LOGGER.error('Invalid target syntax: %s', target)
                continue

            # Target is email, send directly, don't use a target object
            # This also seems works to send to all devices in own account
            if ttype == 'email':
                self.pushbullet.push_note(title, message, email=tname)
                _LOGGER.info('Sent notification to email %s', tname)
                continue

            # Refresh if name not found. While awaiting periodic refresh
            # solution in component, poor mans refresh ;)
            if ttype not in self.pbtargets:
                _LOGGER.error('Invalid target syntax: %s', target)
                continue

            tname = tname.lower()

            if tname not in self.pbtargets[ttype] and not refreshed:
                self.refresh()
                refreshed = True

            # Attempt push_note on a dict value. Keys are types & target
            # name. Dict pbtargets has all *actual* targets.
            try:
                self.pbtargets[ttype][tname].push_note(title, message)
                _LOGGER.info('Sent notification to %s/%s', ttype, tname)
            except KeyError:
                _LOGGER.error('No such target: %s/%s', ttype, tname)
                continue
            except self.pushbullet.errors.PushError:
                _LOGGER.error('Notify failed to: %s/%s', ttype, tname)
                continue
