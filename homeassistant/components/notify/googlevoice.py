"""
homeassistant.components.notify.googlevoice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Google Voice SMS platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.free_mobile/
"""
import logging
from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_PHONE_NUMBER

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['https://github.com/w1ll1am23/pygooglevoice-sms/archive/'
                '7c5ee9969b97a7992fc86a753fe9f20e3ffa3f7c.zip#pygooglevoice-sms==0.0.1']

def get_service(hass, config):
    """ Get the Google Voice SMS notification service. """

    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_USERNAME,
                                     CONF_PASSWORD,
                                     CONF_PHONE_NUMBER]},
                           _LOGGER):
        return None

    return GoogleVoiceSMSNotificationService(config[CONF_USERNAME],
                                      config[CONF_PASSWORD], config[CONF_PHONE_NUMBER])


# pylint: disable=too-few-public-methods
class GoogleVoiceSMSNotificationService(BaseNotificationService):
    """ Implements notification service for the Google Voice SMS service. """

    def __init__(self, username, password, phone_number):
        from googlevoicesms import Voice
        self.voice = Voice()
        self.number = phone_number
        self.username = username
        self.password = password

    def send_message(self, message="", **kwargs):
        """ Send a message to the Free Mobile user cell. """
        resp = self.voice.login(self.username, self.password)
        resp = self.voice.send_sms(self.number, message)

        if resp.status_code == 400:
            _LOGGER.error("At least one parameter is missing")
        elif resp.status_code == 402:
            _LOGGER.error("Too much SMS send in a few time")
        elif resp.status_code == 403:
            _LOGGER.error("Wrong Username/Password")
        elif resp.status_code == 500:
            _LOGGER.error("Server error, try later")
