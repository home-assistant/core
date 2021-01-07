"""Configure number in a device through MQTT topic."""
import logging

import voluptuous as vol

from homeassistant.components import number
from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_DEVICE, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import (
    ATTR_DISCOVERY_HASH,
    CONF_QOS,
    DOMAIN,
    PLATFORMS,
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    subscription,
)
from .. import mqtt
from .debug_info import log_messages
from .discovery import MQTT_DISCOVERY_DONE, MQTT_DISCOVERY_NEW, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

CONF_TOPIC = "topic"
DEFAULT_NAME = "MQTT Number"

PLATFORM_SCHEMA = (
    mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)
)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT number through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT number dynamically through MQTT discovery."""

    async def async_discover(discovery_payload):
        """Discover and add a MQTT number."""
        discovery_data = discovery_payload.discovery_data
        try:
            config = PLATFORM_SCHEMA(discovery_payload)
            await _async_setup_entity(
                config, async_add_entities, config_entry, discovery_data
            )
        except Exception:
            discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
            clear_discovery_hash(hass, discovery_hash)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(number.DOMAIN, "mqtt"), async_discover
    )


async def _async_setup_entity(
    config, async_add_entities, config_entry=None, discovery_data=None
):
    """Set up the MQTT number."""
    async_add_entities([MqttNumber(config, config_entry, discovery_data)])


class MqttNumber(
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    NumberEntity,
):
    """representation of an MQTT number."""

    def __init__(self, config, config_entry, discovery_data):
        """Initialize the MQTT Number."""
        self._config = config
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._sub_state = None

        self._current_number = None

        device_config = config.get(CONF_DEVICE)

        NumberEntity.__init__(self)
        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_data, self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config, config_entry)

    async def async_added_to_hass(self):
        """Subscribe MQTT events."""
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

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""

            try:
                if msg.payload.decode("utf-8").isnumeric():
                    self._current_number = int(msg.payload)
                else:
                    self._current_number = float(msg.payload)
                self.async_write_ha_state()
            except ValueError:
                _LOGGER.warning("We received <%s> which is not a Number", msg.payload)

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_TOPIC],
                    "msg_callback": message_received,
                    "qos": self._config[CONF_QOS],
                    "encoding": None,
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
        await MqttDiscoveryUpdate.async_will_remove_from_hass(self)

    @property
    def value(self):
        """Return the current value."""
        return self._current_number

    async def async_set_value(self, value: float) -> None:
        """Update the current value."""
        if value.is_integer():
            self._current_number = int(value)
        else:
            self._current_number = value

        mqtt.async_publish(
            self.hass,
            self._config[CONF_TOPIC],
            self._current_number,
            self._config[CONF_QOS],
        )

        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of this number."""
        return self._config[CONF_NAME]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return the polling state."""
        return False
