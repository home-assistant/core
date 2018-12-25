"""
Support for MQTT locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.lock import LockDevice
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH, CONF_AVAILABILITY_TOPIC, CONF_STATE_TOPIC,
    CONF_COMMAND_TOPIC, CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE,
    CONF_QOS, CONF_RETAIN, MqttAvailability, MqttDiscoveryUpdate)
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE)
from homeassistant.components import mqtt, lock
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_LOCK = 'payload_lock'
CONF_PAYLOAD_UNLOCK = 'payload_unlock'

DEFAULT_NAME = 'MQTT Lock'
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_LOCK = 'LOCK'
DEFAULT_PAYLOAD_UNLOCK = 'UNLOCK'
DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_LOCK, default=DEFAULT_PAYLOAD_LOCK):
        cv.string,
    vol.Optional(CONF_PAYLOAD_UNLOCK, default=DEFAULT_PAYLOAD_UNLOCK):
        cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT lock panel through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT lock dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add an MQTT lock."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(lock.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT Lock platform."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    async_add_entities([MqttLock(
        config.get(CONF_NAME),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_COMMAND_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_PAYLOAD_LOCK),
        config.get(CONF_PAYLOAD_UNLOCK),
        config.get(CONF_OPTIMISTIC),
        value_template,
        config.get(CONF_AVAILABILITY_TOPIC),
        config.get(CONF_PAYLOAD_AVAILABLE),
        config.get(CONF_PAYLOAD_NOT_AVAILABLE),
        discovery_hash,
    )])


class MqttLock(MqttAvailability, MqttDiscoveryUpdate, LockDevice):
    """Representation of a lock that can be toggled using MQTT."""

    def __init__(self, name, state_topic, command_topic, qos, retain,
                 payload_lock, payload_unlock, optimistic, value_template,
                 availability_topic, payload_available, payload_not_available,
                 discovery_hash):
        """Initialize the lock."""
        MqttAvailability.__init__(self, availability_topic, qos,
                                  payload_available, payload_not_available)
        MqttDiscoveryUpdate.__init__(self, discovery_hash)
        self._state = False
        self._name = name
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._retain = retain
        self._payload_lock = payload_lock
        self._payload_unlock = payload_unlock
        self._optimistic = optimistic
        self._template = value_template
        self._discovery_hash = discovery_hash

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()

        @callback
        def message_received(topic, payload, qos):
            """Handle new MQTT messages."""
            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload)
            if payload == self._payload_lock:
                self._state = True
            elif payload == self._payload_unlock:
                self._state = False

            self.async_schedule_update_ha_state()

        if self._state_topic is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            await mqtt.async_subscribe(
                self.hass, self._state_topic, message_received, self._qos)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    async def async_lock(self, **kwargs):
        """Lock the device.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_lock, self._qos,
            self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            self.async_schedule_update_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the device.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_unlock, self._qos,
            self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.async_schedule_update_ha_state()
