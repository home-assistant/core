"""
Support for MQTT Template switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mqtt_template/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_AVAILABILITY_TOPIC,
    CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE, CONF_QOS, CONF_RETAIN,
    MqttAvailability)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE, CONF_ICON)
import homeassistant.components.mqtt as mqtt
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mqtt_template'

DEPENDENCIES = ['mqtt']

CONF_PAYLOAD_OFF_TEMPLATE = 'payload_off_template'
CONF_PAYLOAD_ON_TEMPLATE = 'payload_on_template'

DEFAULT_NAME = 'MQTT Template Switch'
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Required(CONF_PAYLOAD_ON_TEMPLATE): cv.template,
    vol.Required(CONF_PAYLOAD_OFF_TEMPLATE): cv.template,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the MQTT switch."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    async_add_devices([MqttTemplateSwitch(
        hass,
        config.get(CONF_NAME),
        config.get(CONF_ICON),
        config.get(CONF_STATE_TOPIC),
        config.get(CONF_COMMAND_TOPIC),
        config.get(CONF_AVAILABILITY_TOPIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_OPTIMISTIC),
        config.get(CONF_PAYLOAD_AVAILABLE),
        config.get(CONF_PAYLOAD_NOT_AVAILABLE),
        {
            key: config.get(key) for key in (
                CONF_PAYLOAD_ON_TEMPLATE,
                CONF_PAYLOAD_OFF_TEMPLATE,
                CONF_VALUE_TEMPLATE,
            )
        },
    )])


class MqttTemplateSwitch(MqttAvailability, SwitchDevice):
    """Representation of a switch that can be toggled using MQTT."""

    def __init__(self, hass, name, icon,
                 state_topic, command_topic, availability_topic,
                 qos, retain, optimistic,
                 payload_available, payload_not_available, templates):
        """Initialize the MQTT Template switch."""
        super().__init__(availability_topic, qos, payload_available,
                         payload_not_available)
        self._state = False
        self._name = name
        self._icon = icon
        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._retain = retain
        self._optimistic = optimistic
        self._templates = templates

        for tpl in self._templates.values():
            if tpl is not None:
                tpl.hass = hass

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        yield from super().async_added_to_hass()

        @callback
        def state_message_received(topic, payload, qos):
            """Handle new MQTT state messages."""
            if self._templates[CONF_VALUE_TEMPLATE] is not None:
                payload = \
                    self._templates[CONF_VALUE_TEMPLATE]\
                    .async_render_with_possible_json_value(
                        payload)
            if payload ==\
                    self._templates[CONF_PAYLOAD_ON_TEMPLATE].async_render():
                self._state = True
            elif payload == \
                    self._templates[CONF_PAYLOAD_OFF_TEMPLATE].async_render():
                self._state = False

            self.async_schedule_update_ha_state()

        if self._state_topic is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            yield from mqtt.async_subscribe(
                self.hass, self._state_topic, state_message_received,
                self._qos)

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
    def icon(self):
        """Return the icon."""
        return self._icon

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic,
            self._templates[CONF_PAYLOAD_ON_TEMPLATE].async_render(),
            self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic,
            self._templates[CONF_PAYLOAD_OFF_TEMPLATE].async_render(),
            self._qos, self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.async_schedule_update_ha_state()
