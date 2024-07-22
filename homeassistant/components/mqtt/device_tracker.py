"""Support for tracking MQTT enabled devices identified."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

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
from homeassistant.helpers.typing import ConfigType, VolSchemaType

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import CONF_PAYLOAD_RESET, CONF_STATE_TOPIC
from .mixins import CONF_JSON_ATTRS_TOPIC, MqttEntity, async_setup_entity_entry_helper
from .models import MqttValueTemplate, ReceiveMessage, ReceivePayloadType
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_PAYLOAD_HOME = "payload_home"
CONF_PAYLOAD_NOT_HOME = "payload_not_home"
CONF_SOURCE_TYPE = "source_type"

DEFAULT_PAYLOAD_RESET = "None"
DEFAULT_SOURCE_TYPE = SourceType.GPS


def valid_config(config: ConfigType) -> ConfigType:
    """Check if there is a state topic or json_attributes_topic."""
    if CONF_STATE_TOPIC not in config and CONF_JSON_ATTRS_TOPIC not in config:
        raise vol.Invalid(
            f"Invalid device tracker config, missing {CONF_STATE_TOPIC} or {CONF_JSON_ATTRS_TOPIC}, got: {config}"
        )
    return config


PLATFORM_SCHEMA_MODERN_BASE = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_PAYLOAD_HOME, default=STATE_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_NOT_HOME, default=STATE_NOT_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_RESET, default=DEFAULT_PAYLOAD_RESET): cv.string,
        vol.Optional(CONF_SOURCE_TYPE, default=DEFAULT_SOURCE_TYPE): vol.In(
            SOURCE_TYPES
        ),
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
PLATFORM_SCHEMA_MODERN = vol.All(PLATFORM_SCHEMA_MODERN_BASE, valid_config)


DISCOVERY_SCHEMA = vol.All(
    PLATFORM_SCHEMA_MODERN_BASE.extend({}, extra=vol.REMOVE_EXTRA), valid_config
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT event through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttDeviceTracker,
        device_tracker.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttDeviceTracker(MqttEntity, TrackerEntity):
    """Representation of a device tracker using MQTT."""

    _default_name = None
    _entity_id_format = device_tracker.ENTITY_ID_FORMAT
    _location_name: str | None = None
    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value

    @callback
    def _tracker_message_received(self, msg: ReceiveMessage) -> None:
        """Handle new MQTT messages."""
        payload = self._value_template(msg.payload)
        if not payload.strip():  # No output from template, ignore
            _LOGGER.debug(
                "Ignoring empty payload '%s' after rendering for topic %s",
                payload,
                msg.topic,
            )
            return
        if payload == self._config[CONF_PAYLOAD_HOME]:
            self._location_name = STATE_HOME
        elif payload == self._config[CONF_PAYLOAD_NOT_HOME]:
            self._location_name = STATE_NOT_HOME
        elif payload == self._config[CONF_PAYLOAD_RESET]:
            self._location_name = None
        else:
            if TYPE_CHECKING:
                assert isinstance(msg.payload, str)
            self._location_name = msg.payload

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_STATE_TOPIC, self._tracker_message_received, {"_location_name"}
        )

    @property
    def force_update(self) -> bool:
        """Do not force updates if the state is the same."""
        return False

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

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
