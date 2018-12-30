"""
Support for MQTT binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import mqtt, binary_sensor
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import (
    CONF_FORCE_UPDATE, CONF_NAME, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_ON,
    CONF_PAYLOAD_OFF, CONF_DEVICE_CLASS, CONF_DEVICE)
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH, CONF_AVAILABILITY_TOPIC, CONF_STATE_TOPIC,
    CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE, CONF_QOS,
    MqttAttributes, MqttAvailability, MqttDiscoveryUpdate,
    MqttEntityDeviceInfo, subscription)
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.helpers.event as evt
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MQTT Binary sensor'
CONF_OFF_DELAY = 'off_delay'
CONF_UNIQUE_ID = 'unique_id'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_FORCE_UPDATE = False

DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_RO_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Optional(CONF_OFF_DELAY):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
    # Integrations should never expose unique_id through configuration.
    # This is an exception because MQTT is a message transport, not a protocol
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema).extend(
    mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT binary sensor through configuration.yaml."""
    await _async_setup_entity(config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT binary sensor dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT binary sensor."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(binary_sensor.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(config, async_add_entities, discovery_hash=None):
    """Set up the MQTT binary sensor."""
    async_add_entities([MqttBinarySensor(config, discovery_hash)])


class MqttBinarySensor(MqttAttributes, MqttAvailability, MqttDiscoveryUpdate,
                       MqttEntityDeviceInfo, BinarySensorDevice):
    """Representation a binary sensor that is updated by MQTT."""

    def __init__(self, config, discovery_hash):
        """Initialize the MQTT binary sensor."""
        self._config = config
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._state = None
        self._sub_state = None
        self._delay_listener = None

        availability_topic = config.get(CONF_AVAILABILITY_TOPIC)
        payload_available = config.get(CONF_PAYLOAD_AVAILABLE)
        payload_not_available = config.get(CONF_PAYLOAD_NOT_AVAILABLE)
        qos = config.get(CONF_QOS)
        device_config = config.get(CONF_DEVICE)

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, availability_topic, qos,
                                  payload_available, payload_not_available)
        MqttDiscoveryUpdate.__init__(self, discovery_hash,
                                     self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config)

    async def async_added_to_hass(self):
        """Subscribe mqtt events."""
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
        value_template = self._config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = self.hass

        @callback
        def off_delay_listener(now):
            """Switch device off after a delay."""
            self._delay_listener = None
            self._state = False
            self.async_schedule_update_ha_state()

        @callback
        def state_message_received(_topic, payload, _qos):
            """Handle a new received MQTT state message."""
            value_template = self._config.get(CONF_VALUE_TEMPLATE)
            if value_template is not None:
                payload = value_template.async_render_with_possible_json_value(
                    payload, variables={'entity_id': self.entity_id})
            if payload == self._config.get(CONF_PAYLOAD_ON):
                self._state = True
            elif payload == self._config.get(CONF_PAYLOAD_OFF):
                self._state = False
            else:  # Payload is not for this entity
                _LOGGER.warning('No matching payload found'
                                ' for entity: %s with state_topic: %s',
                                self._config.get(CONF_NAME),
                                self._config.get(CONF_STATE_TOPIC))
                return

            if self._delay_listener is not None:
                self._delay_listener()
                self._delay_listener = None

            off_delay = self._config.get(CONF_OFF_DELAY)
            if (self._state and off_delay is not None):
                self._delay_listener = evt.async_call_later(
                    self.hass, off_delay, off_delay_listener)

            self.async_schedule_update_ha_state()

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state,
            {'state_topic': {'topic': self._config.get(CONF_STATE_TOPIC),
                             'msg_callback': state_message_received,
                             'qos': self._config.get(CONF_QOS)}})

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state)
        await MqttAttributes.async_will_remove_from_hass(self)
        await MqttAvailability.async_will_remove_from_hass(self)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._config.get(CONF_NAME)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def force_update(self):
        """Force update."""
        return self._config.get(CONF_FORCE_UPDATE)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id
