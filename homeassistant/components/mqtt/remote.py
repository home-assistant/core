"""Support for MQTT remotes."""
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.remote import RemoteDevice
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE,
    CONF_ICON,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import (
    CONF_COMMAND_TOPIC,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_UNIQUE_ID,
    MqttAttributes,
    MqttAvailability,
    MqttEntityDeviceInfo,
    subscription,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Remote"
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"

CONF_COMMANDS = "commands"

COMMAND_SCHEMA = vol.Schema(
    {vol.Required(CONF_COMMAND): vol.All(str, vol.Length(min=1))}
)

PLATFORM_SCHEMA = (
    mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
            vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
            vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_COMMANDS, default={}): cv.schema_with_slug_keys(
                COMMAND_SCHEMA
            ),
        }
    )
    .extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)
)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT remote through configuration.yaml."""
    await _async_setup_entity(config, async_add_entities, discovery_info)


async def _async_setup_entity(config, async_add_entities, config_entry=None):
    """Set up the MQTT remote."""
    async_add_entities([MqttRemote(config, config_entry)])


# pylint: disable=too-many-ancestors
class MqttRemote(
    MqttAttributes, MqttAvailability, MqttEntityDeviceInfo, RemoteDevice, RestoreEntity
):
    """Representation of a remote that can be controlled using MQTT."""

    def __init__(self, config, config_entry):
        """Initialize the MQTT remote."""
        self._state = False
        self._sub_state = None

        self._state_on = None
        self._state_off = None
        self._optimistic = None
        self._unique_id = config.get(CONF_UNIQUE_ID)

        # Load config
        self._config = config
        self._optimistic = config[CONF_OPTIMISTIC]
        self._commands = config.get(CONF_COMMANDS)

        device_config = config.get(CONF_DEVICE)

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttEntityDeviceInfo.__init__(self, device_config, config_entry)

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
        await self.device_info_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        value_template = self._config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = self.hass

        @callback
        def state_message_received(msg):
            """Handle a new received MQTT state message."""
            payload = msg.payload

            value_template = self._config.get(CONF_VALUE_TEMPLATE)
            if value_template is not None:
                payload = value_template.async_render_with_possible_json_value(
                    payload, variables={"entity_id": self.entity_id}
                )
            if payload == self._config[CONF_PAYLOAD_ON]:
                self._state = True
            elif payload == self._config[CONF_PAYLOAD_OFF]:
                self._state = False
            else:  # Payload is not for this entity
                _LOGGER.warning(
                    "No matching payload found" " for entity: %s with state_topic: %s",
                    self._config[CONF_NAME],
                    self._config[CONF_STATE_TOPIC],
                )
                return

            self.async_write_ha_state()

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config.get(CONF_STATE_TOPIC),
                    "msg_callback": state_message_received,
                    "qos": self._config[CONF_QOS],
                }
            },
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        await MqttAttributes.async_will_remove_from_hass(self)
        await MqttAvailability.async_will_remove_from_hass(self)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the remote."""
        return self._config[CONF_NAME]

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

    async def async_send_command(self, command, **kwargs):
        """Send a command to the remote.

        This method is a coroutine.
        """
        for single_command in command:
            if single_command in self._commands:
                self._publish_command(self._commands[single_command][CONF_COMMAND])
            else:
                _LOGGER.warning("Unknown command: %s", single_command)

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._publish_command(self._config[CONF_PAYLOAD_ON])

        if self._optimistic:
            # Optimistically assume that remote has changed state.
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self._publish_command(self._config[CONF_PAYLOAD_OFF])

        if self._optimistic:
            # Optimistically assume that remote has changed state.
            self._state = False
            self.async_write_ha_state()

    def _publish_command(self, command):
        mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            command,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
