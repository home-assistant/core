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
    # Integrations should never expose unique_id through configuration.
    # This is an exception because MQTT is a message transport, not a protocol.
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
        self._config = config
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._state = STATE_UNKNOWN
        self._sub_state = None
        self._expiration_trigger = None
        self._attributes = None

        availability_topic = config.get(CONF_AVAILABILITY_TOPIC)
        payload_available = config.get(CONF_PAYLOAD_AVAILABLE)
        payload_not_available = config.get(CONF_PAYLOAD_NOT_AVAILABLE)
        qos = config.get(CONF_QOS)
        device_config = config.get(CONF_DEVICE)

        MqttAvailability.__init__(self, availability_topic, qos,
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
        self._config = config
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
            # auto-expire enabled?
            expire_after = self._config.get(CONF_EXPIRE_AFTER)
            if expire_after is not None and expire_after > 0:
                # Reset old trigger
                if self._expiration_trigger:
                    self._expiration_trigger()
                    self._expiration_trigger = None

                # Set new trigger
                expiration_at = (
                    dt_util.utcnow() + timedelta(seconds=expire_after))

                self._expiration_trigger = async_track_point_in_utc_time(
                    self.hass, self.value_is_expired, expiration_at)

            json_attributes = set(self._config.get(CONF_JSON_ATTRS))
            if json_attributes:
                self._attributes = {}
                try:
                    json_dict = json.loads(payload)
                    if isinstance(json_dict, dict):
                        attrs = {k: json_dict[k] for k in
                                 json_attributes & json_dict.keys()}
                        self._attributes = attrs
                    else:
                        _LOGGER.warning("JSON result was not a dictionary")
                except ValueError:
                    _LOGGER.warning("MQTT payload could not be parsed as JSON")
                    _LOGGER.debug("Erroneous JSON: %s", payload)

            if template is not None:
                payload = template.async_render_with_possible_json_value(
                    payload, self._state)
            self._state = payload
            self.async_schedule_update_ha_state()

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state,
            {'state_topic': {'topic': self._config.get(CONF_STATE_TOPIC),
                             'msg_callback': message_received,
                             'qos': self._config.get(CONF_QOS)}})

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
        return self._config.get(CONF_ICON)

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._config.get(CONF_DEVICE_CLASS)
