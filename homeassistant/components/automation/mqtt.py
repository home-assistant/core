"""
Offer MQTT listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#mqtt-trigger
"""
import logging

import homeassistant.components.mqtt as mqtt

DEPENDENCIES = ['mqtt']

CONF_TOPIC = 'topic'
CONF_PAYLOAD = 'payload'


def trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    topic = config.get(CONF_TOPIC)
    payload = config.get(CONF_PAYLOAD)

    if topic is None:
        logging.getLogger(__name__).error(
            "Missing configuration key %s", CONF_TOPIC)
        return False

    def mqtt_automation_listener(msg_topic, msg_payload, qos):
        """Listen for MQTT messages."""
        if payload is None or payload == msg_payload:
            action()

    mqtt.subscribe(hass, topic, mqtt_automation_listener)

    return True
