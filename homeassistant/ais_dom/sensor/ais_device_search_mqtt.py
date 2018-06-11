"""
Support for MQTT sensors search in app.
"""
import asyncio
import logging
import json
from homeassistant.core import callback
from homeassistant.const import (CONF_NAME)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, MqttAvailability)
from homeassistant.helpers.entity import Entity
import homeassistant.components.mqtt as mqtt

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'MQTT Sensor'
DEFAULT_FORCE_UPDATE = False
DEPENDENCIES = ['mqtt']
MQTT_DEVICES = []
NET_DEVICES = []
DOM_DEVICES = []


def get_text():
    global MQTT_DEVICES
    global NET_DEVICES
    global DOM_DEVICES
    """Return the state of the entity."""
    info = ""
    if len(MQTT_DEVICES) > 0:
        info = "+sterowalne urządzenia w brokerze mqtt (" + str(
            len(MQTT_DEVICES)) + "):\n"
        for d in MQTT_DEVICES:
            info += str(d) + "\n"
    if len(NET_DEVICES) > 0:
        info += "+sterowalne urządzenia w sieci (" + str(
            len(NET_DEVICES)) + "):\n"
        for d in NET_DEVICES:
            info += str(d) + "\n"
    if len(DOM_DEVICES) > 0:
        info += "+głośniki AIS dom (" + str(len(DOM_DEVICES)) + "):\n"
        for d in DOM_DEVICES:
            info += str(d) + "\n"
    return info


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):

    async_add_devices([MqttSensor(
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC)
    )])


class MqttSensor(MqttAvailability, Entity):
    """Representation of a sensor that can be updated using MQTT."""

    def __init__(self, name, state_topic):
        """Initialize the sensor."""
        super().__init__(None, None, None, None)
        self._name = name
        self._state_topic = state_topic

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        yield from super().async_added_to_hass()

        @callback
        def message_received(topic, payload, qos):
            global MQTT_DEVICES
            """Handle new MQTT messages."""
            try:
                message = json.loads(payload)
                statusNet = message.get("StatusNET", None)
                if statusNet is not None:
                    _LOGGER.info("statusNet: " + str(statusNet))
                    _LOGGER.info("statusNet type: " + str(type(statusNet)))
                    # check if it is already added or not
                    device_info = "#"
                    device_info += statusNet["Hostname"]
                    device_info += ", " + statusNet["IPAddress"]
                    device_info += ":80"
                    device_not_exist = True
                    for d in (MQTT_DEVICES):
                        if (str(d) == device_info):
                            device_not_exist = False
                    if device_not_exist:
                        MQTT_DEVICES.append(device_info)

            except Exception as e:
                _LOGGER.info("Error: " + str(e))
            self.async_schedule_update_ha_state()

        yield from mqtt.async_subscribe(
            self.hass, self._state_topic, message_received, 2)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {}
        attr['text'] = get_text()
        return attr

    @property
    def state(self):
        return ''
