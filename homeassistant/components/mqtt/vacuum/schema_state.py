"""Support for a State MQTT vacuum."""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    ENTITY_ID_FORMAT,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    CONF_NAME,
    STATE_IDLE,
    STATE_PAUSED,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.json import json_loads_object

from .. import subscription
from ..config import MQTT_BASE_SCHEMA
from ..const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
)
from ..debug_info import log_messages
from ..mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, warn_for_legacy_schema
from ..models import ReceiveMessage
from ..util import get_mqtt_data, valid_publish_topic
from .const import MQTT_VACUUM_ATTRIBUTES_BLOCKED
from .schema import MQTT_VACUUM_SCHEMA, services_to_strings, strings_to_services

SERVICE_TO_STRING: dict[VacuumEntityFeature, str] = {
    VacuumEntityFeature.START: "start",
    VacuumEntityFeature.PAUSE: "pause",
    VacuumEntityFeature.STOP: "stop",
    VacuumEntityFeature.RETURN_HOME: "return_home",
    VacuumEntityFeature.FAN_SPEED: "fan_speed",
    VacuumEntityFeature.BATTERY: "battery",
    VacuumEntityFeature.STATUS: "status",
    VacuumEntityFeature.SEND_COMMAND: "send_command",
    VacuumEntityFeature.LOCATE: "locate",
    VacuumEntityFeature.CLEAN_SPOT: "clean_spot",
}

STRING_TO_SERVICE = {v: k for k, v in SERVICE_TO_STRING.items()}


DEFAULT_SERVICES = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.CLEAN_SPOT
)
ALL_SERVICES = (
    DEFAULT_SERVICES
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.SEND_COMMAND
)

BATTERY = "battery_level"
FAN_SPEED = "fan_speed"
STATE = "state"

POSSIBLE_STATES: dict[str, str] = {
    STATE_IDLE: STATE_IDLE,
    STATE_DOCKED: STATE_DOCKED,
    STATE_ERROR: STATE_ERROR,
    STATE_PAUSED: STATE_PAUSED,
    STATE_RETURNING: STATE_RETURNING,
    STATE_CLEANING: STATE_CLEANING,
}

CONF_SUPPORTED_FEATURES = ATTR_SUPPORTED_FEATURES
CONF_PAYLOAD_TURN_ON = "payload_turn_on"
CONF_PAYLOAD_TURN_OFF = "payload_turn_off"
CONF_PAYLOAD_RETURN_TO_BASE = "payload_return_to_base"
CONF_PAYLOAD_STOP = "payload_stop"
CONF_PAYLOAD_CLEAN_SPOT = "payload_clean_spot"
CONF_PAYLOAD_LOCATE = "payload_locate"
CONF_PAYLOAD_START = "payload_start"
CONF_PAYLOAD_PAUSE = "payload_pause"
CONF_SET_FAN_SPEED_TOPIC = "set_fan_speed_topic"
CONF_FAN_SPEED_LIST = "fan_speed_list"
CONF_SEND_COMMAND_TOPIC = "send_command_topic"

DEFAULT_NAME = "MQTT State Vacuum"
DEFAULT_RETAIN = False
DEFAULT_SERVICE_STRINGS = services_to_strings(DEFAULT_SERVICES, SERVICE_TO_STRING)
DEFAULT_PAYLOAD_RETURN_TO_BASE = "return_to_base"
DEFAULT_PAYLOAD_STOP = "stop"
DEFAULT_PAYLOAD_CLEAN_SPOT = "clean_spot"
DEFAULT_PAYLOAD_LOCATE = "locate"
DEFAULT_PAYLOAD_START = "start"
DEFAULT_PAYLOAD_PAUSE = "pause"

_FEATURE_PAYLOADS = {
    VacuumEntityFeature.START: CONF_PAYLOAD_START,
    VacuumEntityFeature.STOP: CONF_PAYLOAD_STOP,
    VacuumEntityFeature.PAUSE: CONF_PAYLOAD_PAUSE,
    VacuumEntityFeature.CLEAN_SPOT: CONF_PAYLOAD_CLEAN_SPOT,
    VacuumEntityFeature.LOCATE: CONF_PAYLOAD_LOCATE,
    VacuumEntityFeature.RETURN_HOME: CONF_PAYLOAD_RETURN_TO_BASE,
}

PLATFORM_SCHEMA_STATE_MODERN = (
    MQTT_BASE_SCHEMA.extend(
        {
            vol.Optional(CONF_FAN_SPEED_LIST, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(
                CONF_PAYLOAD_CLEAN_SPOT, default=DEFAULT_PAYLOAD_CLEAN_SPOT
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_LOCATE, default=DEFAULT_PAYLOAD_LOCATE
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_RETURN_TO_BASE, default=DEFAULT_PAYLOAD_RETURN_TO_BASE
            ): cv.string,
            vol.Optional(CONF_PAYLOAD_START, default=DEFAULT_PAYLOAD_START): cv.string,
            vol.Optional(CONF_PAYLOAD_PAUSE, default=DEFAULT_PAYLOAD_PAUSE): cv.string,
            vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): cv.string,
            vol.Optional(CONF_SEND_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_SET_FAN_SPEED_TOPIC): valid_publish_topic,
            vol.Optional(CONF_STATE_TOPIC): valid_publish_topic,
            vol.Optional(
                CONF_SUPPORTED_FEATURES, default=DEFAULT_SERVICE_STRINGS
            ): vol.All(cv.ensure_list, [vol.In(STRING_TO_SERVICE.keys())]),
            vol.Optional(CONF_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        }
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_VACUUM_SCHEMA.schema)
)

# Configuring MQTT Vacuums under the vacuum platform key was deprecated in
# HA Core 2022.6;
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA_STATE = vol.All(
    warn_for_legacy_schema(VACUUM_DOMAIN),
)

DISCOVERY_SCHEMA_STATE = PLATFORM_SCHEMA_STATE_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entity_state(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None,
) -> None:
    """Set up a State MQTT Vacuum."""
    async_add_entities([MqttStateVacuum(hass, config, config_entry, discovery_data)])


class MqttStateVacuum(MqttEntity, StateVacuumEntity):
    """Representation of a MQTT-controlled state vacuum."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_VACUUM_ATTRIBUTES_BLOCKED

    _command_topic: str | None
    _set_fan_speed_topic: str | None
    _send_command_topic: str | None
    _payloads: dict[str, str | None]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the vacuum."""
        self._state_attrs: dict[str, Any] = {}

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA_STATE

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        supported_feature_strings: list[str] = config[CONF_SUPPORTED_FEATURES]
        self._attr_supported_features = strings_to_services(
            supported_feature_strings, STRING_TO_SERVICE
        )
        self._attr_fan_speed_list = config[CONF_FAN_SPEED_LIST]
        self._command_topic = config.get(CONF_COMMAND_TOPIC)
        self._set_fan_speed_topic = config.get(CONF_SET_FAN_SPEED_TOPIC)
        self._send_command_topic = config.get(CONF_SEND_COMMAND_TOPIC)

        self._payloads = {
            key: config.get(key)
            for key in (
                CONF_PAYLOAD_START,
                CONF_PAYLOAD_PAUSE,
                CONF_PAYLOAD_STOP,
                CONF_PAYLOAD_RETURN_TO_BASE,
                CONF_PAYLOAD_CLEAN_SPOT,
                CONF_PAYLOAD_LOCATE,
            )
        }

    def _update_state_attributes(self, payload: dict[str, Any]) -> None:
        """Update the entity state attributes."""
        self._state_attrs.update(payload)
        self._attr_fan_speed = self._state_attrs.get(FAN_SPEED, 0)
        self._attr_battery_level = max(0, min(100, self._state_attrs.get(BATTERY, 0)))

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        topics: dict[str, Any] = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle state MQTT message."""
            payload = json_loads_object(msg.payload)
            if STATE in payload and (
                (state := payload[STATE]) in POSSIBLE_STATES or state is None
            ):
                self._attr_state = (
                    POSSIBLE_STATES[cast(str, state)] if payload[STATE] else None
                )
                del payload[STATE]
            self._update_state_attributes(payload)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if state_topic := self._config.get(CONF_STATE_TOPIC):
            topics["state_position_topic"] = {
                "topic": state_topic,
                "msg_callback": state_message_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }
        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def _async_publish_command(self, feature: VacuumEntityFeature) -> None:
        """Check for a missing feature or command topic."""
        if self._command_topic is None or self.supported_features & feature == 0:
            return

        await self.async_publish(
            self._command_topic,
            self._payloads[_FEATURE_PAYLOADS[feature]],
            qos=self._config[CONF_QOS],
            retain=self._config[CONF_RETAIN],
            encoding=self._config[CONF_ENCODING],
        )
        self.async_write_ha_state()

    async def async_start(self) -> None:
        """Start the vacuum."""
        await self._async_publish_command(VacuumEntityFeature.START)

    async def async_pause(self) -> None:
        """Pause the vacuum."""
        await self._async_publish_command(VacuumEntityFeature.PAUSE)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        await self._async_publish_command(VacuumEntityFeature.STOP)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Tell the vacuum to return to its dock."""
        await self._async_publish_command(VacuumEntityFeature.RETURN_HOME)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        await self._async_publish_command(VacuumEntityFeature.CLEAN_SPOT)

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum (usually by playing a song)."""
        await self._async_publish_command(VacuumEntityFeature.LOCATE)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if (
            self._set_fan_speed_topic is None
            or (self.supported_features & VacuumEntityFeature.FAN_SPEED == 0)
            or (fan_speed not in self.fan_speed_list)
        ):
            return
        await self.async_publish(
            self._set_fan_speed_topic,
            fan_speed,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        if (
            self._send_command_topic is None
            or self.supported_features & VacuumEntityFeature.SEND_COMMAND == 0
        ):
            return
        if isinstance(params, dict):
            message: dict[str, Any] = {"command": command}
            message.update(params)
            payload = json_dumps(message)
        else:
            payload = command
        await self.async_publish(
            self._send_command_topic,
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
