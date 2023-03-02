"""Support for tracking MQTT enabled devices identified."""
from __future__ import annotations

from collections.abc import Callable
import functools

import voluptuous as vol

from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import (
    SOURCE_TYPES,
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_NAME,
    CONF_VALUE_TEMPLATE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import MQTT_RO_SCHEMA
from .const import CONF_PAYLOAD_RESET, CONF_QOS, CONF_STATE_TOPIC
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
    warn_for_legacy_schema,
)
from .models import MqttValueTemplate, ReceiveMessage, ReceivePayloadType
from .util import get_mqtt_data

CONF_PAYLOAD_HOME = "payload_home"
CONF_PAYLOAD_NOT_HOME = "payload_not_home"
CONF_SOURCE_TYPE = "source_type"

DEFAULT_PAYLOAD_RESET = "None"
DEFAULT_SOURCE_TYPE = SourceType.GPS

PLATFORM_SCHEMA_MODERN = MQTT_RO_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_HOME, default=STATE_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_NOT_HOME, default=STATE_NOT_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_RESET, default=DEFAULT_PAYLOAD_RESET): cv.string,
        vol.Optional(CONF_SOURCE_TYPE, default=DEFAULT_SOURCE_TYPE): vol.In(
            SOURCE_TYPES
        ),
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)

# Configuring MQTT Device Trackers under the device_tracker platform key was deprecated
# in HA Core 2022.6
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA = vol.All(warn_for_legacy_schema(device_tracker.DOMAIN))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT device_tracker through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, device_tracker.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT Device Tracker entity."""
    async_add_entities([MqttDeviceTracker(hass, config, config_entry, discovery_data)])


class MqttDeviceTracker(MqttEntity, TrackerEntity):
    """Representation of a device tracker using MQTT."""

    _entity_id_format = device_tracker.ENTITY_ID_FORMAT
    _value_template: Callable[..., ReceivePayloadType]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the tracker."""
        self._location_name: str | None = None
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            payload: ReceivePayloadType = self._value_template(msg.payload)
            if payload == self._config[CONF_PAYLOAD_HOME]:
                self._location_name = STATE_HOME
            elif payload == self._config[CONF_PAYLOAD_NOT_HOME]:
                self._location_name = STATE_NOT_HOME
            elif payload == self._config[CONF_PAYLOAD_RESET]:
                self._location_name = None
            else:
                assert isinstance(msg.payload, str)
                self._location_name = msg.payload

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        self._sub_state = subscription.async_prepare_subscribe_topics(
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

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def latitude(self) -> float | None:
        """Return latitude if provided in extra_state_attributes or None."""
        if (
            self.extra_state_attributes is not None
            and ATTR_LATITUDE in self.extra_state_attributes
        ):
            latitude: float = self.extra_state_attributes[ATTR_LATITUDE]
            return latitude
        return None

    @property
    def location_accuracy(self) -> int:
        """Return location accuracy if provided in extra_state_attributes or None."""
        if (
            self.extra_state_attributes is not None
            and ATTR_GPS_ACCURACY in self.extra_state_attributes
        ):
            accuracy: int = self.extra_state_attributes[ATTR_GPS_ACCURACY]
            return accuracy
        return 0

    @property
    def longitude(self) -> float | None:
        """Return longitude if provided in extra_state_attributes or None."""
        if (
            self.extra_state_attributes is not None
            and ATTR_LONGITUDE in self.extra_state_attributes
        ):
            longitude: float = self.extra_state_attributes[ATTR_LONGITUDE]
            return longitude
        return None

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        return self._location_name

    @property
    def source_type(self) -> SourceType | str:
        """Return the source type, eg gps or router, of the device."""
        source_type: SourceType | str = self._config[CONF_SOURCE_TYPE]
        return source_type
