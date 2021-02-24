"""Support for tracking MQTT enabled devices identified through discovery."""
import functools
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

from .. import subscription
from ... import mqtt
from ..const import CONF_QOS, CONF_STATE_TOPIC
from ..debug_info import log_messages
from ..mixins import (
    MQTT_AVAILABILITY_SCHEMA,
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    MQTT_JSON_ATTRS_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
)

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_HOME = "payload_home"
CONF_PAYLOAD_NOT_HOME = "payload_not_home"
CONF_SOURCE_TYPE = "source_type"

PLATFORM_SCHEMA_DISCOVERY = (
    mqtt.MQTT_RO_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_PAYLOAD_HOME, default=STATE_HOME): cv.string,
            vol.Optional(CONF_PAYLOAD_NOT_HOME, default=STATE_NOT_HOME): cv.string,
            vol.Optional(CONF_SOURCE_TYPE): vol.In(SOURCE_TYPES),
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(MQTT_AVAILABILITY_SCHEMA.schema)
    .extend(MQTT_JSON_ATTRS_SCHEMA.schema)
)


async def async_setup_entry_from_discovery(hass, config_entry, async_add_entities):
    """Set up MQTT device tracker dynamically through MQTT discovery."""

    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(
        hass, device_tracker.DOMAIN, setup, PLATFORM_SCHEMA_DISCOVERY
    )


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT Device Tracker entity."""
    async_add_entities([MqttDeviceTracker(hass, config, config_entry, discovery_data)])


class MqttDeviceTracker(MqttEntity, TrackerEntity):
    """Representation of a device tracker using MQTT."""

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the tracker."""
        self._location_name = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA_DISCOVERY

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
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return self._config.get(CONF_SOURCE_TYPE)
