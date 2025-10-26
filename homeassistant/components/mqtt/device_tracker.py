"""Support for tracking MQTT enabled devices identified."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import device_tracker
from homeassistant.components.device_tracker import SourceType, TrackerEntity
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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, VolSchemaType

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import (
    CONF_JSON_ATTRS_TEMPLATE,
    CONF_JSON_ATTRS_TOPIC,
    CONF_PAYLOAD_RESET,
    CONF_STATE_TOPIC,
)
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import MqttValueTemplate, ReceiveMessage
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

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
        vol.Optional(CONF_SOURCE_TYPE, default=DEFAULT_SOURCE_TYPE): vol.Coerce(
            SourceType
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
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        self._attr_source_type = self._config[CONF_SOURCE_TYPE]

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
            self._attr_location_name = STATE_HOME
        elif payload == self._config[CONF_PAYLOAD_NOT_HOME]:
            self._attr_location_name = STATE_NOT_HOME
        elif payload == self._config[CONF_PAYLOAD_RESET]:
            self._attr_location_name = None
        else:
            if TYPE_CHECKING:
                assert isinstance(msg.payload, str)
            self._attr_location_name = msg.payload

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_STATE_TOPIC, self._tracker_message_received, {"_attr_location_name"}
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    @callback
    def _process_update_extra_state_attributes(
        self, extra_state_attributes: dict[str, Any]
    ) -> None:
        """Extract the location from the extra state attributes."""
        if (
            ATTR_LATITUDE in extra_state_attributes
            or ATTR_LONGITUDE in extra_state_attributes
        ):
            latitude: float | None
            longitude: float | None
            gps_accuracy: float
            # Reset manually set location to allow automatic zone detection
            self._attr_location_name = None
            if isinstance(
                latitude := extra_state_attributes.get(ATTR_LATITUDE), (int, float)
            ) and isinstance(
                longitude := extra_state_attributes.get(ATTR_LONGITUDE), (int, float)
            ):
                self._attr_latitude = latitude
                self._attr_longitude = longitude
            else:
                # Invalid or incomplete coordinates, reset location
                self._attr_latitude = None
                self._attr_longitude = None
                _LOGGER.warning(
                    "Extra state attributes received at % and template %s "
                    "contain invalid or incomplete location info. Got %s",
                    self._config.get(CONF_JSON_ATTRS_TEMPLATE),
                    self._config.get(CONF_JSON_ATTRS_TOPIC),
                    extra_state_attributes,
                )

            if ATTR_GPS_ACCURACY in extra_state_attributes:
                if isinstance(
                    gps_accuracy := extra_state_attributes[ATTR_GPS_ACCURACY],
                    (int, float),
                ):
                    self._attr_location_accuracy = gps_accuracy
                else:
                    _LOGGER.warning(
                        "Extra state attributes received at % and template %s "
                        "contain invalid GPS accuracy setting, "
                        "gps_accuracy was set to 0 as the default. Got %s",
                        self._config.get(CONF_JSON_ATTRS_TEMPLATE),
                        self._config.get(CONF_JSON_ATTRS_TOPIC),
                        extra_state_attributes,
                    )
                    self._attr_location_accuracy = 0

            else:
                self._attr_location_accuracy = 0

        self._attr_extra_state_attributes = {
            attribute: value
            for attribute, value in extra_state_attributes.items()
            if attribute not in {ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE}
        }
