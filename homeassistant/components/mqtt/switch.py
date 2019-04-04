"""
Support for MQTT switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.components import mqtt, switch
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    CONF_DEVICE, CONF_ICON, CONF_NAME, CONF_OPTIMISTIC, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_VALUE_TEMPLATE, STATE_ON)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import (
    ATTR_DISCOVERY_HASH, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN,
    CONF_STATE_TOPIC, CONF_UNIQUE_ID, MqttAttributes, MqttAvailability,
    MqttDiscoveryUpdate, MqttEntityDeviceInfo, subscription)
from .discovery import MQTT_DISCOVERY_NEW, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = 'MQTT Switch'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False
CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_STATE_ON): cv.string,
    vol.Optional(CONF_STATE_OFF): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema).extend(
    mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT switch through configuration.yaml."""
    await _async_setup_entity(config, async_add_entities,
                              discovery_info)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT switch dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT switch."""
        try:
            discovery_hash = discovery_payload.pop(ATTR_DISCOVERY_HASH)
            config = PLATFORM_SCHEMA(discovery_payload)
            await _async_setup_entity(config, async_add_entities, config_entry,
                                      discovery_hash)
        except Exception:
            if discovery_hash:
                clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(switch.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(config, async_add_entities, config_entry=None,
                              discovery_hash=None):
    """Set up the MQTT switch."""
    async_add_entities([MqttSwitch(config, config_entry, discovery_hash)])


# pylint: disable=too-many-ancestors
class MqttSwitch(MqttAttributes, MqttAvailability, MqttDiscoveryUpdate,
                 MqttEntityDeviceInfo, SwitchDevice, RestoreEntity):
    """Representation of a switch that can be toggled using MQTT."""

    def __init__(self, config, config_entry, discovery_hash):
        """Initialize the MQTT switch."""
        self._state = False
        self._sub_state = None

        self._state_on = None
        self._state_off = None
        self._optimistic = None
        self._unique_id = config.get(CONF_UNIQUE_ID)

        # Load config
        self._setup_from_config(config)

        device_config = config.get(CONF_DEVICE)

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_hash,
                                     self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config, config_entry)

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA(discovery_payload)
        self._setup_from_config(config)
        await self.attributes_discovery_update(config)
        await self.availability_discovery_update(config)
        await self.device_info_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._config = config

        state_on = config.get(CONF_STATE_ON)
        self._state_on = state_on if state_on else config.get(CONF_PAYLOAD_ON)

        state_off = config.get(CONF_STATE_OFF)
        self._state_off = state_off if state_off else \
            config.get(CONF_PAYLOAD_OFF)

        self._optimistic = config.get(CONF_OPTIMISTIC)

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        template = self._config.get(CONF_VALUE_TEMPLATE)
        if template is not None:
            template.hass = self.hass

        @callback
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            payload = msg.payload
            if template is not None:
                payload = template.async_render_with_possible_json_value(
                    payload)
            if payload == self._state_on:
                self._state = True
            elif payload == self._state_off:
                self._state = False

            self.async_write_ha_state()

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            self._sub_state = await subscription.async_subscribe_topics(
                self.hass, self._sub_state,
                {CONF_STATE_TOPIC:
                 {'topic': self._config.get(CONF_STATE_TOPIC),
                  'msg_callback': state_message_received,
                  'qos': self._config.get(CONF_QOS)}})

        if self._optimistic:
            last_state = await self.async_get_last_state()
            if last_state:
                self._state = last_state.state == STATE_ON

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
        """Return the name of the switch."""
        return self._config.get(CONF_NAME)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon."""
        return self._config.get(CONF_ICON)

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_COMMAND_TOPIC),
            self._config.get(CONF_PAYLOAD_ON),
            self._config.get(CONF_QOS),
            self._config.get(CONF_RETAIN))
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config.get(CONF_COMMAND_TOPIC),
            self._config.get(CONF_PAYLOAD_OFF),
            self._config.get(CONF_QOS),
            self._config.get(CONF_RETAIN))
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.async_write_ha_state()
