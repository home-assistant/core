"""
homeassistant.components.notify.pushbullet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
PushBullet platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.pushbullet/
"""
import logging

from homeassistant.components.notify import ATTR_TITLE, BaseNotificationService
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pushbullet.py==0.9.0']
ATTR_TARGET='target'


def get_service(hass, config):
    """ Get the PushBullet notification service. """
    from pushbullet import PushBullet
    from pushbullet import InvalidKeyError

    if CONF_API_KEY not in config:
        _LOGGER.error("Unable to find config key '%s'", CONF_API_KEY)
        return None

    try:
        pb = PushBullet(config[CONF_API_KEY])

    except InvalidKeyError:
        _LOGGER.error(
            "Wrong API key supplied. "
            "Get it at https://www.pushbullet.com/account")
        return None

    return PushBulletNotificationService(pb)


# pylint: disable=too-few-public-methods
class PushBulletNotificationService(BaseNotificationService):
    """ Implements notification service for Pushbullet. """

    def __init__(self, pb):
        self.pushbullet = pb
        self.refresh()

    def refresh(self):
        ''' Refresh devices, contacts, channels, etc '''
        self.pushbullet.refresh()

        self.pbtargets = {
            'devices'  :
                {target.nickname: target for target in self.pushbullet.devices},
            'contacts' :
                {target.email: target for target in self.pushbullet.contacts},
            'channels' :
                {target.channel_tag: target for target in self.pushbullet.channels},
        }
        import pprint
        _LOGGER.error(pprint.pformat(self.pbtargets))

    def send_message(self, message=None, **kwargs):
        """ Send a message to a user. """
        targets = kwargs.get(ATTR_TARGET)
        title = kwargs.get(ATTR_TITLE)

        if targets:
            # Make list if not so
            if not isinstance(targets, list):
                targets = [targets]

            # Main loop, Process all targets specified
            for ttype,tname in [target.split('.') for target in targets]:
                if ttype = 'device' and tname = '':
                    # Allow for 'normal' push, combined with other targets
                    self.pushbullet.push_note(None, message)
                    continue

                try:
                    self.pbtargets[ttype+'s'][tname].push_note(None, message)
                except KeyError:
                    _LOGGER.error('No such target: %s.%s'%(ttype, tname))
                    continue
                except self.pushbullet.errors.PushError as e:
                    _LOGGER.error('Sending message failed to: %s.%s, %s'%
                        (ttype, tname, e))
                    self.refresh()
                    continue
                _LOGGER.info('Sent notification to: %s.%s'%(ttype, tname))

        else:
            # Backward compatebility, notify all devices in own account
            self.pushbullet.push_note(None, message)

