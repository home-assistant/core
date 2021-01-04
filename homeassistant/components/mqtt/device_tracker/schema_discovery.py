"""Support for tracking MQTT enabled devices identified through discovery."""
import logging

import voluptuous as vol

from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import SOURCE_TYPES
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICE,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .. import (
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    subscription,
)
from ... import mqtt
from ..const import ATTR_DISCOVERY_HASH, CONF_QOS, CONF_STATE_TOPIC
from ..debug_info import log_messages
from ..discovery import MQTT_DISCOVERY_DONE, MQTT_DISCOVERY_NEW, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_HOME = "payload_home"
CONF_PAYLOAD_NOT_HOME = "payload_not_home"
CONF_SOURCE_TYPE = "source_type"

PLATFORM_SCHEMA_DISCOVERY = (
    mqtt.MQTT_RO_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_DEVICE): mqtt.MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_PAYLOAD_HOME, default=STATE_HOME): cv.string,
            vol.Optional(CONF_PAYLOAD_NOT_HOME, default=STATE_NOT_HOME): cv.string,
            vol.Optional(CONF_SOURCE_TYPE): vol.In(SOURCE_TYPES),
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(mqtt.MQTT_JSON_ATTRS_SCHEMA.schema)
)


async def async_setup_entry_from_discovery(hass, config_entry, async_add_entities):
    """Set up MQTT device tracker dynamically through MQTT discovery."""

    async def async_discover(discovery_payload):
        """Discover and add an MQTT device tracker."""
        discovery_data = discovery_payload.discovery_data
        try:
            config = PLATFORM_SCHEMA_DISCOVERY(discovery_payload)
            await _async_setup_entity(
                hass, config, async_add_entities, config_entry, discovery_data
            )
        except Exception:
            discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
            clear_discovery_hash(hass, discovery_hash)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(device_tracker.DOMAIN, "mqtt"), async_discover
    )


async def _async_setup_entity(
    hass, config, async_add_entities, config_entry=None, discovery_data=None
):
    """Set up the MQTT Device Tracker entity."""
    async_add_entities([MqttDeviceTracker(hass, config, config_entry, discovery_data)])


class MqttDeviceTracker(
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
    TrackerEntity,
):
    """Representation of a device tracker using MQTT."""

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the tracker."""
        self.hass = hass
        self._location_name = None
        self._sub_state = None
        self._unique_id = config.get(CONF_UNIQUE_ID)

        # Load config
        self._setup_from_config(config)

        device_config = config.get(CONF_DEVICE)

        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_data, self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, device_config, config_entry)

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = PLATFORM_SCHEMA_DISCOVERY(discovery_payload)
        self._setup_from_config(config)
        await self.attributes_discovery_update(config)
        await self.availability_discovery_update(config)
        await self.device_info_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._config = config

        value_template = self._config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = self.hass

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""
            payload = msg.payload
            value_template = self._config.get(CONF_VALUE_TEMPLATE)
            if value_template is not None:
                payload = value_template.async_render_with_possible_json_value(payload)
            if payload == self._config[CONF_PAYLOAD_HOME]:
                self._location_name = STATE_HOME
            elif payload == self._config[CONF_PAYLOAD_NOT_HOME]:
                self._location_name = STATE_NOT_HOME
            else:
                self._location_name = msg.payload

            self.async_write_ha_state()

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_STATE_TOPIC],
                    "msg_callback": message_received,
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
        await MqttDiscoveryUpdate.async_will_remove_from_hass(self)

    @property
    def icon(self):
        """Return the icon of the device."""
        return self._config.get(CONF_ICON)

    @property
    def latitude(self):
        """Return latitude if provided in device_state_attributes or None."""
        if (
            self.device_state_attributes is not None
            and ATTR_LATITUDE in self.device_state_attributes
        ):
            return self.device_state_attributes[ATTR_LATITUDE]
        return None

    @property
    def location_accuracy(self):
        """Return location accuracy if provided in device_state_attributes or None."""
        if (
            self.device_state_attributes is not None
            and ATTR_GPS_ACCURACY in self.device_state_attributes
        ):
            return self.device_state_attributes[ATTR_GPS_ACCURACY]
        return None

    @property
    def longitude(self):
        """Return longitude if provided in device_state_attributes or None."""
        if (
            self.device_state_attributes is not None
            and ATTR_LONGITUDE in self.device_state_attributes
        ):
            return self.device_state_attributes[ATTR_LONGITUDE]
        return None

    @property
    def location_name(self):
        """Return a location name for the current location of the device."""
        return self._location_name

    @property
    def name(self):
        """Return the name of the device tracker."""
        return self._config.get(CONF_NAME)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return self._config.get(CONF_SOURCE_TYPE)
