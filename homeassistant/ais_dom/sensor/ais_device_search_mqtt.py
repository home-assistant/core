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
from homeassistant.util import slugify


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
            info += "#" + d["FriendlyName"] + ", http://" + d["IPAddress"] + ":80" + "\n"
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
        config.get(CONF_STATE_TOPIC),
        hass
    )])


class MqttSensor(MqttAvailability, Entity):
    """Representation of a sensor that can be updated using MQTT."""

    def __init__(self, name, state_topic, hass):
        """Initialize the sensor."""
        super().__init__(None, None, None, None)
        self._name = name
        self._state_topic = state_topic
        self.hass = hass

    def discover_sensors(self, sensor, topic):
        conf_state_topic = "tele/" + topic + "/SENSOR"
        if sensor == "SI7021":
            configuration_topic = "core_homeassistant/sensor/" + topic + "_9/config"
            name = 'Temperatura ' + topic[-6:]
            j_payload = {
                'name': name,
                'unique_id': slugify(name),
                'state_topic': conf_state_topic,
                'icon': 'mdi:temperature-celsius',
                'unit_of_measurement': '°C',
                'value_template': "{{ value_json['SI7021'].Temperature | round(2)}}"
            }
            self.hass.async_create_task(
                self.hass.services.async_call('mqtt', 'publish', {
                    'topic': configuration_topic,
                    'payload': json.dumps(j_payload)
                })
            )
            configuration_topic = "core_homeassistant/sensor/" + topic + "_10/config"
            name = 'Wilgotność ' + topic[-6:]
            j_payload = {
                'name': name,
                'unique_id': slugify(name),
                'state_topic': conf_state_topic,
                'icon': 'mdi:temperature-celsius',
                'unit_of_measurement': '%',
                'value_template': "{{ value_json['SI7021'].Humidity | round(2)}}"
            }
            self.hass.async_create_task(
                self.hass.services.async_call('mqtt', 'publish', {
                    'topic': configuration_topic,
                    'payload': json.dumps(j_payload)
                })
            )
        elif sensor == "ENERGY":
            configuration_topic = "core_homeassistant/sensor/" + topic + "_9/config"
            name = 'Energia bieżąca moc ' + topic[-6:]
            j_payload = {
                'name': name,
                'unique_id': slugify(name),
                'state_topic': conf_state_topic,
                'icon': 'mdi:flash-red-eye',
                'unit_of_measurement': 'W',
                'value_template': "{{ value_json['ENERGY'].Power | round(2)}}"
            }
            self.hass.async_create_task(
                self.hass.services.async_call('mqtt', 'publish', {
                    'topic': configuration_topic,
                    'payload': json.dumps(j_payload)
                })
            )
            configuration_topic = "core_homeassistant/sensor/" + topic + "_10/config"
            name = 'Energia całkowita ' + topic[-6:]
            j_payload = {
                'name': name,
                'unique_id': slugify(name),
                'state_topic': conf_state_topic,
                'icon': 'mdi:flash-red-eye',
                'unit_of_measurement': 'kWh',
                'value_template': "{{ value_json['ENERGY'].Total | round(2)}}"
            }
            self.hass.async_create_task(
                self.hass.services.async_call('mqtt', 'publish', {
                    'topic': configuration_topic,
                    'payload': json.dumps(j_payload)
                })
            )
            configuration_topic = "core_homeassistant/sensor/" + topic + "_11/config"
            name = 'Energia dzisiaj ' + topic[-6:]
            j_payload = {
                'name': name,
                'unique_id': slugify(name),
                'state_topic': conf_state_topic,
                'icon': 'mdi:flash-red-eye',
                'unit_of_measurement': 'kWh',
                'value_template': "{{ value_json['ENERGY'].Today | round(2)}}"
            }
            self.hass.async_create_task(
                self.hass.services.async_call('mqtt', 'publish', {
                    'topic': configuration_topic,
                    'payload': json.dumps(j_payload)
                })
            )
            configuration_topic = "core_homeassistant/sensor/" + topic + "_12/config"
            name = 'Energia wczoraj ' + topic[-6:]
            j_payload = {
                'name': name,
                'unique_id': slugify(name),
                'state_topic': conf_state_topic,
                'icon': 'mdi:flash-red-eye',
                'unit_of_measurement': 'kWh',
                'value_template': "{{ value_json['ENERGY'].Yesterday | round(2)}}"
            }
            self.hass.async_create_task(
                self.hass.services.async_call('mqtt', 'publish', {
                    'topic': configuration_topic,
                    'payload': json.dumps(j_payload)
                })
            )
            configuration_topic = "core_homeassistant/sensor/" + topic + "_13/config"
            name = 'Energia bieżące napięcie ' + topic[-6:]
            j_payload = {
                'name': name,
                'unique_id': slugify(name),
                'state_topic': conf_state_topic,
                'icon': 'mdi:flash-red-eye',
                'unit_of_measurement': 'V',
                'value_template': "{{ value_json['ENERGY'].Voltage | round(2)}}"
            }
            self.hass.async_create_task(
                self.hass.services.async_call('mqtt', 'publish', {
                    'topic': configuration_topic,
                    'payload': json.dumps(j_payload)
                })
            )
            configuration_topic = "core_homeassistant/sensor/" + topic + "_14/config"
            name = 'Energia bieżące natężenie ' + topic[-6:]
            j_payload = {
                'name': name,
                'unique_id': slugify(name),
                'state_topic': conf_state_topic,
                'icon': 'mdi:flash-auto',
                'unit_of_measurement': 'A',
                'value_template': "{{ value_json['ENERGY'].Current | round(2)}}"
            }
            self.hass.async_create_task(
                self.hass.services.async_call('mqtt', 'publish', {
                    'topic': configuration_topic,
                    'payload': json.dumps(j_payload)
                })
            )

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
                ip_address = ""
                friendly_name = ""
                sensors = ""
                topic = topic.replace("stat/", "").replace("/STATUS", "")
                if "Status" in message:
                    friendly_name = message.get("Status")["FriendlyName"][0]
                elif "StatusNET" in message:
                    ip_address = message.get("StatusNET")["IPAddress"]
                    topic = topic[0:-1]
                elif "StatusSNS" in message:
                    sensors = message.get("StatusSNS")
                    topic = topic[0:-2]
                else:
                    return
                # check if device exists in collection
                device_not_exist = True
                for d in MQTT_DEVICES:
                    if d["topic"] == topic:
                        device_not_exist = False
                        if ip_address != "":
                            d["IPAddress"] = ip_address
                        if friendly_name != "":
                            d["FriendlyName"] = friendly_name
                        if sensors != "":
                            d["Sensors"] = sensors
                            # since we have message about sensors, we can try to discover this sensor in home assistant
                            for s, v in sensors.items():
                                if s in ('SI7021', 'ENERGY'):
                                    self.discover_sensors(s, topic)
                if device_not_exist:
                    MQTT_DEVICES.append(
                        {"topic": topic, "FriendlyName": friendly_name, "IPAddress": ip_address, "Sensors": sensors})

            except Exception as e:
                _LOGGER.info("Error: " + str(e))
            self.async_schedule_update_ha_state()

        # @callback
        def async_disco_message_received(topic, payload, qos):
            if payload != "":
                _LOGGER.info('DISCO: ' + str(topic) + " p:" + str(payload))
                try:
                    j_payload = json.loads(payload)
                    if 'state_topic' in j_payload:
                        # we can add some more info about device
                        # j_payload["icon"] = "mdi:power-plug"
                        if 'unique_id' not in j_payload:
                            uid = topic.replace("homeassistant/", "").replace("/config", "")
                            j_payload["unique_id"] = uid
                        # fix for the ifan
                        if 'command_topic' in j_payload:
                            t = j_payload["command_topic"]
                            if 'dom_SONOFF_IFAN' in t and 'POWER2' in t:
                                t = t.replace("POWER2", "FanSpeed")
                                j_payload["command_topic"] = t
                                j_payload["payload_on"] = 1
                                j_payload["payload_off"] = 0
                                j_payload["value_template"] = "{% if value_json.FanSpeed == 1 %}1{% else %}0{% endif %}"
                            elif 'dom_SONOFF_IFAN' in t and 'POWER3' in t:
                                t = t.replace("POWER3", "FanSpeed")
                                j_payload["command_topic"] = t
                                j_payload["payload_on"] = 2
                                j_payload["payload_off"] = 0
                                j_payload["value_template"] = "{% if value_json.FanSpeed == 2 %}2{% else %}0{% endif %}"
                            elif 'dom_SONOFF_IFAN' in t and 'POWER4' in t:
                                t = t.replace("POWER4", "FanSpeed")
                                j_payload["command_topic"] = t
                                j_payload["payload_on"] = 3
                                j_payload["payload_off"] = 0
                                j_payload["value_template"] = "{% if value_json.FanSpeed == 3 %}3{% else %}0{% endif %}"
                        # to discover the device
                        self.hass.async_create_task(
                            self.hass.services.async_call('mqtt', 'publish', {
                                'topic': "core_" + topic,
                                'payload': json.dumps(j_payload)
                            })
                        )
                        if 'command_topic' in j_payload:
                            command_topic = j_payload["command_topic"].replace("/POWER", "/status")
                            # to discover the sensors on device
                            self.hass.bus.fire('search_for_sensors', {
                                'topic': command_topic
                            })
                except Exception as e:
                    _LOGGER.error('async_disco_message_received: ' + str(e))

        yield from mqtt.async_subscribe(
            self.hass, self._state_topic, message_received, 2)
        # subscribe to discovery, to add some more info about device
        yield from mqtt.async_subscribe(
            self.hass, 'homeassistant/#', async_disco_message_received, 2)

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
