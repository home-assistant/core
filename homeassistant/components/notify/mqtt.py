"""
homeassistant.components.notify.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
MQTT platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.mqtt/
"""
import logging
import homeassistant.components.mqtt as mqtt
from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']


def get_service(hass, config):
    """ Get the MQTT notification service. """

    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['topic', 'qos', 'retain']},
                           _LOGGER):
        return None

    return MQTTNotificationService(hass, config['topic'], config['qos'],
                                   config['retain'])


# pylint: disable=too-few-public-methods
class MQTTNotificationService(BaseNotificationService):
    """ Implements notification service for the MQTT service. """

    def __init__(self, hass, topic, qos, retain):
        self.hass = hass
        self._topic = topic
        self._qos = qos
        self._retain = retain

    def send_message(self, message="", **kwargs):
        mqtt.publish(self.hass, self._topic, message,
                     self._qos, self._retain)
