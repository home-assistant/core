"""
Support for MQTT sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mqtt/
"""
import logging
import json
from datetime import timedelta
from typing import Optional

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import sensor
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH, CONF_AVAILABILITY_TOPIC, CONF_STATE_TOPIC,
    CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE, CONF_QOS,
    MqttAvailability, MqttDiscoveryUpdate, MqttEntityDeviceInfo, subscription)
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_FORCE_UPDATE, CONF_NAME, CONF_VALUE_TEMPLATE, STATE_UNKNOWN,
    CONF_UNIT_OF_MEASUREMENT, CONF_ICON, CONF_DEVICE_CLASS, CONF_DEVICE)
from homeassistant.helpers.entity import Entity
from homeassistant.components import mqtt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_EXPIRE_AFTER = 'expire_after'
CONF_JSON_ATTRS = 'json_attributes'
CONF_UNIQUE_ID = 'unique_id'

DEFAULT_NAME = 'MQTT Sensor'
DEFAULT_FORCE_UPDATE = False
DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_RO_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_JSON_ATTRS, default=[]): cv.ensure_list_csv,
    vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    # Integrations shouldn't never expose unique_id through configuration
    # this here is an exception because MQTT is a msg transport, not a protocol
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT sensors through configuration.yaml."""
    await _async_setup_entity(config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT sensors dynamically through MQTT discovery."""
    async def async_discover_sensor(discovery_payload):
        """Discover and add a discovered MQTT sensor."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(hass,
                             MQTT_DISCOVERY_NEW.format(sensor.DOMAIN, 'mqtt'),
                             async_discover_sensor)


async def _async_setup_entity(config: ConfigType, async_add_entities,
                              discovery_hash=None):
    """Set up MQTT sensor."""
    async_add_entities([MqttSensor(config, discovery_hash)])


class MqttSensor(MqttAvailability, MqttDiscoveryUpdate, MqttEntityDeviceInfo,
                 Entity):
    """Representation of a sensor that can be updated using MQTT."""

    def __init__(self, config, discovery_hash):
        """Initialize the sensor."""
        self._state = STATE_UNKNOWN
        self._sub_state = None
        self._expiration_trigger = None
        self._attributes = None

        self._name = None
        self._state_topic = None
        self._qos = None
        self._unit_of_measurement = None
        self._force_update = None
        self._template = None
        self._expire_after = None
        self._icon = None
        self._device_class = None
        self._json_attributes = None
        self._unique_id = None

        # Load config
        self._setup_from_config(config)

        availability_topic = config.get(CONF_AVAILABILITY_TOPIC)
        payload_available = config.get(CONF_PAYLOAD_AVAILABLE)
        payload_not_available = config.get(CONF_PAYLOAD_NOT_AVAILABLE)
        device_config = config.get(CONF_DEVICE)

        MqttAvailability.__init__(self, availability_topic, self._qos,
                                  payload_available, payload_not_available)
        MqttDiscoveryUpdate.__init__(self, discovery_hash,
                                     self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config)

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA(discovery_payload)
        self._setup_from_config(config)
        await self.availability_discovery_update(config)
        await self._subscribe_topics()
        self.async_schedule_update_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._name = config.get(CONF_NAME)
        self._state_topic = config.get(CONF_STATE_TOPIC)
        self._qos = config.get(CONF_QOS)
        self._unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._force_update = config.get(CONF_FORCE_UPDATE)
        self._expire_after = config.get(CONF_EXPIRE_AFTER)
        self._icon = config.get(CONF_ICON)
        self._device_class = config.get(CONF_DEVICE_CLASS)
        self._template = config.get(CONF_VALUE_TEMPLATE)
        self._json_attributes = set(config.get(CONF_JSON_ATTRS))
        self._unique_id = config.get(CONF_UNIQUE_ID)

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        if self._template is not None:
            self._template.hass = self.hass

        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
            # auto-expire enabled?
            if self._expire_after is not None and self._expire_after > 0:
                # Reset old trigger
                if self._expiration_trigger:
                    self._expiration_trigger()
                    self._expiration_trigger = None

                # Set new trigger
                expiration_at = (
                    dt_util.utcnow() + timedelta(seconds=self._expire_after))

                self._expiration_trigger = async_track_point_in_utc_time(
                    self.hass, self.value_is_expired, expiration_at)

            if self._json_attributes:
                self._attributes = {}
                try:
                    json_dict = json.loads(payload)
                    if isinstance(json_dict, dict):
                        attrs = {k: json_dict[k] for k in
                                 self._json_attributes & json_dict.keys()}
                        self._attributes = attrs
                    else:
                        _LOGGER.warning("JSON result was not a dictionary")
                except ValueError:
                    _LOGGER.warning("MQTT payload could not be parsed as JSON")
                    _LOGGER.debug("Erroneous JSON: %s", payload)

            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload, self._state)
            self._state = payload
            self.async_schedule_update_ha_state()

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state,
            {'state_topic': {'topic': self._state_topic,
                             'msg_callback': message_received,
                             'qos': self._qos}})

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        await subscription.async_unsubscribe_topics(self.hass, self._sub_state)
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
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

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
        return self._icon

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class
