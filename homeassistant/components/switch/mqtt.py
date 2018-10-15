"""
Support for MQTT switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mqtt/
"""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH, CONF_STATE_TOPIC, CONF_COMMAND_TOPIC,
    CONF_AVAILABILITY_TOPIC, CONF_PAYLOAD_AVAILABLE,
    CONF_PAYLOAD_NOT_AVAILABLE, CONF_QOS, CONF_RETAIN, MqttAvailability,
    MqttDiscoveryUpdate, MqttEntityDeviceInfo)
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE, CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON, CONF_ICON, STATE_ON, CONF_DEVICE)
from homeassistant.components import mqtt, switch
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.helpers.restore_state import async_get_last_state

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = 'MQTT Switch'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_OPTIMISTIC = False
CONF_UNIQUE_ID = 'unique_id'
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
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT switch through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities,
                              discovery_info)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT switch dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT switch."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(switch.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up the MQTT switch."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    newswitch = MqttSwitch(
        config.get(CONF_NAME),
        config.get(CONF_ICON),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_COMMAND_TOPIC),
        config.get(CONF_AVAILABILITY_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_PAYLOAD_ON),
        config.get(CONF_PAYLOAD_OFF),
        config.get(CONF_STATE_ON),
        config.get(CONF_STATE_OFF),
        config.get(CONF_OPTIMISTIC),
        config.get(CONF_PAYLOAD_AVAILABLE),
        config.get(CONF_PAYLOAD_NOT_AVAILABLE),
        config.get(CONF_UNIQUE_ID),
        value_template,
        config.get(CONF_DEVICE),
        discovery_hash,
    )

    async_add_entities([newswitch])


class MqttSwitch(MqttAvailability, MqttDiscoveryUpdate, MqttEntityDeviceInfo,
                 SwitchDevice):
    """Representation of a switch that can be toggled using MQTT."""

    def __init__(self, name, icon,
                 state_topic, command_topic, availability_topic,
                 qos, retain, payload_on, payload_off, state_on,
                 state_off, optimistic, payload_available,
                 payload_not_available, unique_id: Optional[str],
                 value_template, device_config: Optional[ConfigType],
                 discovery_hash):
        """Initialize the MQTT switch."""
        MqttAvailability.__init__(self, availability_topic, qos,
                                  payload_available, payload_not_available)
        MqttDiscoveryUpdate.__init__(self, discovery_hash)
        MqttEntityDeviceInfo.__init__(self, device_config)
        self._state = False
        self._name = name
        self._icon = icon
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._retain = retain
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._state_on = state_on if state_on else self._payload_on
        self._state_off = state_off if state_off else self._payload_off
        self._optimistic = optimistic
        self._template = value_template
        self._unique_id = unique_id
        self._discovery_hash = discovery_hash

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await MqttAvailability.async_added_to_hass(self)
        await MqttDiscoveryUpdate.async_added_to_hass(self)

        @callback
        def state_message_received(topic, payload, qos):
            """Handle new MQTT state messages."""
            if self._template is not None:
                payload = self._template.async_render_with_possible_json_value(
                    payload)
            if payload == self._state_on:
                self._state = True
            elif payload == self._state_off:
                self._state = False

            self.async_schedule_update_ha_state()

        if self._state_topic is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            await mqtt.async_subscribe(
                self.hass, self._state_topic, state_message_received,
                self._qos)

        if self._optimistic:
            last_state = await async_get_last_state(self.hass,
                                                    self.entity_id)
            if last_state:
                self._state = last_state.state == STATE_ON

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

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
        return self._icon

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_on, self._qos,
            self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_off, self._qos,
            self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.async_schedule_update_ha_state()
