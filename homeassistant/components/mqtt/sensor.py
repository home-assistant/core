"""Support for MQTT sensors."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import sensor
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    STATE_CLASSES_SCHEMA,
    RestoreSensor,
    SensorDeviceClass,
    SensorExtraStoredData,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import subscription
from .config import MQTT_RO_SCHEMA
from .const import CONF_ENCODING, CONF_QOS, CONF_STATE_TOPIC, PAYLOAD_NONE
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttAvailability,
    MqttEntity,
    async_setup_entry_helper,
)
from .models import (
    MqttValueTemplate,
    PayloadSentinel,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import get_mqtt_data

_LOGGER = logging.getLogger(__name__)

CONF_EXPIRE_AFTER = "expire_after"
CONF_LAST_RESET_TOPIC = "last_reset_topic"
CONF_LAST_RESET_VALUE_TEMPLATE = "last_reset_value_template"
CONF_SUGGESTED_DISPLAY_PRECISION = "suggested_display_precision"

MQTT_SENSOR_ATTRIBUTES_BLOCKED = frozenset(
    {
        sensor.ATTR_LAST_RESET,
        sensor.ATTR_STATE_CLASS,
    }
)

DEFAULT_NAME = "MQTT Sensor"
DEFAULT_FORCE_UPDATE = False


_PLATFORM_SCHEMA_BASE = MQTT_RO_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): vol.Any(DEVICE_CLASSES_SCHEMA, None),
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_LAST_RESET_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_SUGGESTED_DISPLAY_PRECISION): cv.positive_int,
        vol.Optional(CONF_STATE_CLASS): vol.Any(STATE_CLASSES_SCHEMA, None),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.Any(cv.string, None),
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(
    # Deprecated in HA Core 2021.11.0 https://github.com/home-assistant/core/pull/54840
    # Removed in HA Core 2023.6.0
    cv.removed(CONF_LAST_RESET_TOPIC),
    _PLATFORM_SCHEMA_BASE,
)

DISCOVERY_SCHEMA = vol.All(
    # Deprecated in HA Core 2021.11.0 https://github.com/home-assistant/core/pull/54840
    # Removed in HA Core 2023.6.0
    cv.removed(CONF_LAST_RESET_TOPIC),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT sensor through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, sensor.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT sensor."""
    async_add_entities([MqttSensor(hass, config, config_entry, discovery_data)])


class MqttSensor(MqttEntity, RestoreSensor):
    """Representation of a sensor that can be updated using MQTT."""

    _default_name = DEFAULT_NAME
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_last_reset: datetime | None = None
    _attributes_extra_blocked = MQTT_SENSOR_ATTRIBUTES_BLOCKED
    _expire_after: int | None
    _expired: bool | None
    _template: Callable[[ReceivePayloadType, PayloadSentinel], ReceivePayloadType]
    _last_reset_template: Callable[[ReceivePayloadType], ReceivePayloadType]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the sensor."""
        self._expiration_trigger: CALLBACK_TYPE | None = None
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    async def mqtt_async_added_to_hass(self) -> None:
        """Restore state for entities with expire_after set."""
        last_state: State | None
        last_sensor_data: SensorExtraStoredData | None
        if (
            (_expire_after := self._expire_after) is not None
            and _expire_after > 0
            and (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            and (last_sensor_data := await self.async_get_last_sensor_data())
            is not None
            # We might have set up a trigger already after subscribing from
            # MqttEntity.async_added_to_hass(), then we should not restore state
            and not self._expiration_trigger
        ):
            expiration_at = last_state.last_changed + timedelta(seconds=_expire_after)
            if expiration_at < (time_now := dt_util.utcnow()):
                # Skip reactivating the sensor
                _LOGGER.debug("Skip state recovery after reload for %s", self.entity_id)
                return
            self._expired = False
            self._attr_native_value = last_sensor_data.native_value

            self._expiration_trigger = async_track_point_in_utc_time(
                self.hass, self._value_is_expired, expiration_at
            )
            _LOGGER.debug(
                (
                    "State recovered after reload for %s, remaining time before"
                    " expiring %s"
                ),
                self.entity_id,
                expiration_at - time_now,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Remove exprire triggers."""
        # Clean up expire triggers
        if self._expiration_trigger:
            _LOGGER.debug("Clean up expire after trigger for %s", self.entity_id)
            self._expiration_trigger()
            self._expiration_trigger = None
            self._expired = False
        await MqttEntity.async_will_remove_from_hass(self)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_force_update = config[CONF_FORCE_UPDATE]
        self._attr_suggested_display_precision = config.get(
            CONF_SUGGESTED_DISPLAY_PRECISION
        )
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_state_class = config.get(CONF_STATE_CLASS)

        self._expire_after = config.get(CONF_EXPIRE_AFTER)
        if self._expire_after is not None and self._expire_after > 0:
            self._expired = True
        else:
            self._expired = None

        self._template = MqttValueTemplate(
            self._config.get(CONF_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value
        self._last_reset_template = MqttValueTemplate(
            self._config.get(CONF_LAST_RESET_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        topics: dict[str, dict[str, Any]] = {}

        def _update_state(msg: ReceiveMessage) -> None:
            # auto-expire enabled?
            if self._expire_after is not None and self._expire_after > 0:
                # When self._expire_after is set, and we receive a message, assume
                # device is not expired since it has to be to receive the message
                self._expired = False

                # Reset old trigger
                if self._expiration_trigger:
                    self._expiration_trigger()

                # Set new trigger
                expiration_at = dt_util.utcnow() + timedelta(seconds=self._expire_after)

                self._expiration_trigger = async_track_point_in_utc_time(
                    self.hass, self._value_is_expired, expiration_at
                )

            payload = self._template(msg.payload, PayloadSentinel.DEFAULT)
            if payload is PayloadSentinel.DEFAULT:
                return
            new_value = str(payload)
            if self._numeric_state_expected:
                if new_value == "":
                    _LOGGER.debug("Ignore empty state from '%s'", msg.topic)
                elif new_value == PAYLOAD_NONE:
                    self._attr_native_value = None
                else:
                    self._attr_native_value = new_value
                return
            if self.device_class in {None, SensorDeviceClass.ENUM}:
                self._attr_native_value = new_value
                return
            try:
                if (payload_datetime := dt_util.parse_datetime(new_value)) is None:
                    raise ValueError
            except ValueError:
                _LOGGER.warning(
                    "Invalid state message '%s' from '%s'", msg.payload, msg.topic
                )
                self._attr_native_value = None
                return
            if self.device_class == SensorDeviceClass.DATE:
                self._attr_native_value = payload_datetime.date()
                return
            self._attr_native_value = payload_datetime

        def _update_last_reset(msg: ReceiveMessage) -> None:
            payload = self._last_reset_template(msg.payload)

            if not payload:
                _LOGGER.debug("Ignoring empty last_reset message from '%s'", msg.topic)
                return
            try:
                last_reset = dt_util.parse_datetime(str(payload))
                if last_reset is None:
                    raise ValueError
                self._attr_last_reset = last_reset
            except ValueError:
                _LOGGER.warning(
                    "Invalid last_reset message '%s' from '%s'", msg.payload, msg.topic
                )

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            _update_state(msg)
            if CONF_LAST_RESET_VALUE_TEMPLATE in self._config:
                _update_last_reset(msg)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        topics["state_topic"] = {
            "topic": self._config[CONF_STATE_TOPIC],
            "msg_callback": message_received,
            "qos": self._config[CONF_QOS],
            "encoding": self._config[CONF_ENCODING] or None,
        }

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @callback
    def _value_is_expired(self, *_: datetime) -> None:
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._expired = True
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return true if the device is available and value has not expired."""
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return MqttAvailability.available.fget(self) and (  # type: ignore[attr-defined]
            self._expire_after is None or not self._expired
        )
