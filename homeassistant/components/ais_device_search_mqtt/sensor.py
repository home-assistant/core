"""
Support for MQTT sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mqtt/
"""
from datetime import timedelta
import json
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.components import mqtt, sensor
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH,
    CONF_QOS,
    CONF_STATE_TOPIC,
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    subscription,
)
from homeassistant.components.mqtt.discovery import (
    MQTT_DISCOVERY_NEW,
    clear_discovery_hash,
)
from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

_LOGGER = logging.getLogger(__name__)

CONF_EXPIRE_AFTER = "expire_after"
CONF_JSON_ATTRS = "json_attributes"
CONF_UNIQUE_ID = "unique_id"

DEFAULT_NAME = "MQTT Sensor"
DEFAULT_FORCE_UPDATE = False
DEPENDENCIES = ["mqtt"]
SCAN_INTERVAL = timedelta(seconds=600000000)

MQTT_DEVICES = []
NET_DEVICES = []
DOM_DEVICES = []


PLATFORM_SCHEMA = (
    mqtt.MQTT_RO_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_JSON_ATTRS, default=[]): cv.ensure_list_csv,
            vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
            vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        }
    )
    .extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)
)


def get_text():
    global MQTT_DEVICES
    global NET_DEVICES
    global DOM_DEVICES
    """Return the state of the entity."""
    info = ""
    if len(MQTT_DEVICES) > 0:
        info = (
            "\n### Sterowalne urządzenia w brokerze mqtt ("
            + str(len(MQTT_DEVICES))
            + "):\n"
        )
        for d in MQTT_DEVICES:
            info += "- " + d["FriendlyName"] + ", http://" + d["IPAddress"] + "\n"
    if len(NET_DEVICES) > 0:
        info += "\n### Sterowalne urządzenia w sieci (" + str(len(NET_DEVICES)) + "):\n"
        for d in NET_DEVICES:
            info += str(d) + "\n"
    if len(DOM_DEVICES) > 0:
        info += "\n### Bramki AIS dom (" + str(len(DOM_DEVICES)) + "):\n"
        for d in DOM_DEVICES:
            info += str(d) + "\n"
    return info


def get_text_to_say():
    """Return the info about devices"""
    import time

    # Wait for 10 seconds
    time.sleep(10)
    if len(MQTT_DEVICES) > 0 or len(NET_DEVICES) > 0:
        info = ""
    else:
        info = "Nie wykryto sterowanych urządzeń."
    if len(MQTT_DEVICES) > 0:
        info += "Liczba wykrytych sterowalnych urządzeń podłączonych do bramki: " + str(
            len(MQTT_DEVICES)
        )
    if len(NET_DEVICES) > 0:
        if len(MQTT_DEVICES) > 0:
            info += ". "
        info += "Liczba wykrytych sterowalnych urządzeń w sieci: " + str(
            len(NET_DEVICES)
        )
    return info


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT sensors through configuration.yaml."""
    await _async_setup_entity(config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT sensors dynamically through MQTT discovery."""

    async def async_discover_sensor(discovery_payload):
        """Discover and add a discovered MQTT sensor."""
        try:
            discovery_hash = discovery_payload[ATTR_DISCOVERY_HASH]
            config = PLATFORM_SCHEMA(discovery_payload)
            await _async_setup_entity(config, async_add_entities, discovery_hash)
        except Exception:
            if discovery_hash:
                clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(sensor.DOMAIN, "mqtt"), async_discover_sensor
    )


async def _async_setup_entity(
    config: ConfigType, async_add_entities, discovery_hash=None
):
    """Set up MQTT sensor."""
    async_add_entities([MqttSensor(config, discovery_hash)])


class MqttSensor(
    MqttAttributes, MqttAvailability, MqttDiscoveryUpdate, MqttEntityDeviceInfo, Entity
):
    """Representation of a sensor that can be updated using MQTT."""

    def __init__(self, config, discovery_hash):
        """Initialize the sensor."""
        self._config = config
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._state = STATE_UNKNOWN
        self._sub_state = None
        self._expiration_trigger = None
        self._attributes = None

        device_config = config.get(CONF_DEVICE)

        if config.get(CONF_JSON_ATTRS):
            _LOGGER.warning(
                'configuration variable "json_attributes" is '
                'deprecated, replace with "json_attributes_topic"'
            )

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_hash, self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config)

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA(discovery_payload)
        self._config = config
        await self.attributes_discovery_update(config)
        await self.availability_discovery_update(config)
        await self._subscribe_topics()
        self.async_schedule_update_ha_state()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        template = self._config.get(CONF_VALUE_TEMPLATE)
        if template is not None:
            template.hass = self.hass

        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
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
                if device_not_exist:
                    MQTT_DEVICES.append(
                        {
                            "topic": topic,
                            "FriendlyName": friendly_name,
                            "IPAddress": ip_address,
                            "Sensors": sensors,
                        }
                    )

            except Exception as e:
                _LOGGER.info("Error: " + str(e))
            self.async_schedule_update_ha_state()

        # self._sub_state = await subscription.async_subscribe_topics(
        #     self.hass, self._sub_state,
        #     {'state_topic': {'topic': self._config.get(CONF_STATE_TOPIC),
        #                      'msg_callback': message_received,
        #                      'qos': self._config.get(CONF_QOS)}})

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        await MqttAttributes.async_will_remove_from_hass(self)
        await MqttAvailability.async_will_remove_from_hass(self)

    @callback
    def value_is_expired(self, *_):
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._state = STATE_UNKNOWN
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._config.get(CONF_NAME)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._config.get(CONF_UNIT_OF_MEASUREMENT)

    @property
    def force_update(self):
        """Force update."""
        return self._config.get(CONF_FORCE_UPDATE)

    @property
    def state(self):
        """Return the state of the entity."""
        return " "

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon."""
        return self._config.get(CONF_ICON)

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._config.get(CONF_DEVICE_CLASS)
