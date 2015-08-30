"""
homeassistant.components.automation.mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Offers MQTT listening automation rules.
"""
import logging

import homeassistant.components.mqtt as mqtt

DEPENDENCIES = ['mqtt']

CONF_TOPIC = 'mqtt_topic'
CONF_PAYLOAD = 'mqtt_payload'


def register(hass, config, action):
    """ Listen for state changes based on `config`. """
    topic = config.get(CONF_TOPIC)
    payload = config.get(CONF_PAYLOAD)

    if topic is None:
        logging.getLogger(__name__).error(
            "Missing configuration key %s", CONF_TOPIC)
        return False

    def mqtt_automation_listener(msg_topic, msg_payload, qos):
        """ Listens for MQTT messages. """
        if payload is None or payload == msg_payload:
            action()

    mqtt.subscribe(hass, topic, mqtt_automation_listener)

    return True
