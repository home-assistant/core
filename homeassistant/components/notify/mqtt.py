"""
homeassistant.components.notify.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MQTT notification service.

Configuration:

To use the MQTT notifier you will need to add something like the following
to your config/configuration.yaml

notify:
  platform: mqtt
  broker_ip: IP address or hostname obroker
  broker_port: 1883
  publish_topic: home-assistent/notify

VARIABLES:

broker_ip
*Required
If you don't run a local MQTT broker, as an alternative use the public one for
the Eclipse Fundation at iot.eclipse.org

broker_port
*Required
The default port is 1883 for MQTT.

publish_topic
*Required
All messages are published to the given topic.


To see the messages subscribe to the topic "home-assistent/notify"
$ mosquitto_sub -h [IP address of broker] -t "home-assistent/notify"

"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)
_CLIENT_NAME = "home-assistent"


def get_service(hass, config):
    """ Get the MQTT notification service. """

    if not validate_config(config,
                           {DOMAIN: ['broker_ip',
                                     'broker_port',
                                     'publish_topic']},
                           _LOGGER):
        return None

    try:
        # pylint: disable=unused-variable
        import paho.mqtt.client as mqtt

    except ImportError:
        _LOGGER.exception(
            "Unable to import paho-mqtt. "
            "Did you maybe not install the 'paho-mqtt' package?")

        return None

    try:
        return MqttNotificationService(
            config[DOMAIN]['broker_ip'],
            config[DOMAIN]['broker_port'],
            config[DOMAIN]['publish_topic'])

    except OSError:
        _LOGGER.error(
            "Unable to connect to broker . "
            "Please check your setting.")


# pylint: disable=too-few-public-methods
class MqttNotificationService(BaseNotificationService):
    """ Implements notification service for MQTT. """

    def __init__(self, broker_ip, broker_port, publish_topic):
        import paho.mqtt.client as mqtt

        self._broker_ip = broker_ip
        self._broker_port = broker_port
        self._publish_topic = publish_topic

        self.mqtt = mqtt.Client(_CLIENT_NAME)
        self.mqtt.connect(self._broker_ip,
                          port=int(self._broker_port),
                          keepalive=60)


    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        payload = message

        self.mqtt.publish(self._publish_topic,
                          payload=payload,
                          qos=0,
                          retain=False)
        self.mqtt.disconnect()
