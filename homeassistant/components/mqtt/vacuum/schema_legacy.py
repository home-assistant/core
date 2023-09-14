"""Support for Legacy MQTT vacuum.

The legacy schema for MQTT vacuum was deprecated with HA Core 2023.8.0
and is will be removed with HA Core 2024.2.0
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_STATUS,
    ENTITY_ID_FORMAT,
    VacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_NAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .. import subscription
from ..config import MQTT_BASE_SCHEMA
from ..const import CONF_COMMAND_TOPIC, CONF_ENCODING, CONF_QOS, CONF_RETAIN
from ..debug_info import log_messages
from ..mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity
from ..models import (
    MqttValueTemplate,
    PayloadSentinel,
    ReceiveMessage,
    ReceivePayloadType,
)
from ..util import get_mqtt_data, valid_publish_topic
from .const import MQTT_VACUUM_ATTRIBUTES_BLOCKED
from .schema import MQTT_VACUUM_SCHEMA, services_to_strings, strings_to_services

SERVICE_TO_STRING = {
    VacuumEntityFeature.TURN_ON: "turn_on",
    VacuumEntityFeature.TURN_OFF: "turn_off",
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
    VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.TURN_OFF
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

CONF_SUPPORTED_FEATURES = ATTR_SUPPORTED_FEATURES
CONF_BATTERY_LEVEL_TEMPLATE = "battery_level_template"
CONF_BATTERY_LEVEL_TOPIC = "battery_level_topic"
CONF_CHARGING_TEMPLATE = "charging_template"
CONF_CHARGING_TOPIC = "charging_topic"
CONF_CLEANING_TEMPLATE = "cleaning_template"
CONF_CLEANING_TOPIC = "cleaning_topic"
CONF_DOCKED_TEMPLATE = "docked_template"
CONF_DOCKED_TOPIC = "docked_topic"
CONF_ERROR_TEMPLATE = "error_template"
CONF_ERROR_TOPIC = "error_topic"
CONF_FAN_SPEED_LIST = "fan_speed_list"
CONF_FAN_SPEED_TEMPLATE = "fan_speed_template"
CONF_FAN_SPEED_TOPIC = "fan_speed_topic"
CONF_PAYLOAD_CLEAN_SPOT = "payload_clean_spot"
CONF_PAYLOAD_LOCATE = "payload_locate"
CONF_PAYLOAD_RETURN_TO_BASE = "payload_return_to_base"
CONF_PAYLOAD_START_PAUSE = "payload_start_pause"
CONF_PAYLOAD_STOP = "payload_stop"
CONF_PAYLOAD_TURN_OFF = "payload_turn_off"
CONF_PAYLOAD_TURN_ON = "payload_turn_on"
CONF_SEND_COMMAND_TOPIC = "send_command_topic"
CONF_SET_FAN_SPEED_TOPIC = "set_fan_speed_topic"

DEFAULT_NAME = "MQTT Vacuum"
DEFAULT_PAYLOAD_CLEAN_SPOT = "clean_spot"
DEFAULT_PAYLOAD_LOCATE = "locate"
DEFAULT_PAYLOAD_RETURN_TO_BASE = "return_to_base"
DEFAULT_PAYLOAD_START_PAUSE = "start_pause"
DEFAULT_PAYLOAD_STOP = "stop"
DEFAULT_PAYLOAD_TURN_OFF = "turn_off"
DEFAULT_PAYLOAD_TURN_ON = "turn_on"
DEFAULT_RETAIN = False
DEFAULT_SERVICE_STRINGS = services_to_strings(DEFAULT_SERVICES, SERVICE_TO_STRING)

MQTT_LEGACY_VACUUM_ATTRIBUTES_BLOCKED = MQTT_VACUUM_ATTRIBUTES_BLOCKED | frozenset(
    {ATTR_STATUS}
)

PLATFORM_SCHEMA_LEGACY_MODERN = (
    MQTT_BASE_SCHEMA.extend(
        {
            vol.Inclusive(CONF_BATTERY_LEVEL_TEMPLATE, "battery"): cv.template,
            vol.Inclusive(CONF_BATTERY_LEVEL_TOPIC, "battery"): valid_publish_topic,
            vol.Inclusive(CONF_CHARGING_TEMPLATE, "charging"): cv.template,
            vol.Inclusive(CONF_CHARGING_TOPIC, "charging"): valid_publish_topic,
            vol.Inclusive(CONF_CLEANING_TEMPLATE, "cleaning"): cv.template,
            vol.Inclusive(CONF_CLEANING_TOPIC, "cleaning"): valid_publish_topic,
            vol.Inclusive(CONF_DOCKED_TEMPLATE, "docked"): cv.template,
            vol.Inclusive(CONF_DOCKED_TOPIC, "docked"): valid_publish_topic,
            vol.Inclusive(CONF_ERROR_TEMPLATE, "error"): cv.template,
            vol.Inclusive(CONF_ERROR_TOPIC, "error"): valid_publish_topic,
            vol.Optional(CONF_FAN_SPEED_LIST, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Inclusive(CONF_FAN_SPEED_TEMPLATE, "fan_speed"): cv.template,
            vol.Inclusive(CONF_FAN_SPEED_TOPIC, "fan_speed"): valid_publish_topic,
            vol.Optional(CONF_NAME): vol.Any(cv.string, None),
            vol.Optional(
                CONF_PAYLOAD_CLEAN_SPOT, default=DEFAULT_PAYLOAD_CLEAN_SPOT
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_LOCATE, default=DEFAULT_PAYLOAD_LOCATE
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_RETURN_TO_BASE, default=DEFAULT_PAYLOAD_RETURN_TO_BASE
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_START_PAUSE, default=DEFAULT_PAYLOAD_START_PAUSE
            ): cv.string,
            vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): cv.string,
            vol.Optional(
                CONF_PAYLOAD_TURN_OFF, default=DEFAULT_PAYLOAD_TURN_OFF
            ): cv.string,
            vol.Optional(
                CONF_PAYLOAD_TURN_ON, default=DEFAULT_PAYLOAD_TURN_ON
            ): cv.string,
            vol.Optional(CONF_SEND_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_SET_FAN_SPEED_TOPIC): valid_publish_topic,
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

DISCOVERY_SCHEMA_LEGACY = PLATFORM_SCHEMA_LEGACY_MODERN.extend(
    {}, extra=vol.REMOVE_EXTRA
)


_COMMANDS = {
    VacuumEntityFeature.TURN_ON: {
        "payload": CONF_PAYLOAD_TURN_ON,
        "status": "Cleaning",
    },
    VacuumEntityFeature.TURN_OFF: {
        "payload": CONF_PAYLOAD_TURN_OFF,
        "status": "Turning Off",
    },
    VacuumEntityFeature.STOP: {
        "payload": CONF_PAYLOAD_STOP,
        "status": "Stopping the current task",
    },
    VacuumEntityFeature.CLEAN_SPOT: {
        "payload": CONF_PAYLOAD_CLEAN_SPOT,
        "status": "Cleaning spot",
    },
    VacuumEntityFeature.LOCATE: {
        "payload": CONF_PAYLOAD_LOCATE,
        "status": "Hi, I'm over here!",
    },
    VacuumEntityFeature.PAUSE: {
        "payload": CONF_PAYLOAD_START_PAUSE,
        "status": "Pausing/Resuming cleaning...",
    },
    VacuumEntityFeature.RETURN_HOME: {
        "payload": CONF_PAYLOAD_RETURN_TO_BASE,
        "status": "Returning home...",
    },
}


async def async_setup_entity_legacy(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None,
) -> None:
    """Set up a MQTT Vacuum Legacy."""
    async_add_entities([MqttVacuum(hass, config, config_entry, discovery_data)])


class MqttVacuum(MqttEntity, VacuumEntity):
    """Representation of a MQTT-controlled legacy vacuum."""

    _default_name = DEFAULT_NAME
    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LEGACY_VACUUM_ATTRIBUTES_BLOCKED

    _command_topic: str | None
    _encoding: str | None
    _qos: bool
    _retain: bool
    _payloads: dict[str, str]
    _send_command_topic: str | None
    _set_fan_speed_topic: str | None
    _state_topics: dict[str, str | None]
    _templates: dict[
        str, Callable[[ReceivePayloadType, PayloadSentinel], ReceivePayloadType]
    ]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the vacuum."""
        self._attr_battery_level = 0
        self._attr_is_on = False
        self._attr_fan_speed = "unknown"

        self._charging = False
        self._cleaning = False
        self._docked = False
        self._error: str | None = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA_LEGACY

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        supported_feature_strings = config[CONF_SUPPORTED_FEATURES]
        self._attr_supported_features = strings_to_services(
            supported_feature_strings, STRING_TO_SERVICE
        )
        self._attr_fan_speed_list = config[CONF_FAN_SPEED_LIST]
        self._qos = config[CONF_QOS]
        self._retain = config[CONF_RETAIN]
        self._encoding = config[CONF_ENCODING] or None

        self._command_topic = config.get(CONF_COMMAND_TOPIC)
        self._set_fan_speed_topic = config.get(CONF_SET_FAN_SPEED_TOPIC)
        self._send_command_topic = config.get(CONF_SEND_COMMAND_TOPIC)

        self._payloads = {
            key: config[key]
            for key in (
                CONF_PAYLOAD_TURN_ON,
                CONF_PAYLOAD_TURN_OFF,
                CONF_PAYLOAD_RETURN_TO_BASE,
                CONF_PAYLOAD_STOP,
                CONF_PAYLOAD_CLEAN_SPOT,
                CONF_PAYLOAD_LOCATE,
                CONF_PAYLOAD_START_PAUSE,
            )
        }
        self._state_topics = {
            key: config.get(key)
            for key in (
                CONF_BATTERY_LEVEL_TOPIC,
                CONF_CHARGING_TOPIC,
                CONF_CLEANING_TOPIC,
                CONF_DOCKED_TOPIC,
                CONF_ERROR_TOPIC,
                CONF_FAN_SPEED_TOPIC,
            )
        }
        self._templates = {
            key: MqttValueTemplate(
                config[key], entity=self
            ).async_render_with_possible_json_value
            for key in (
                CONF_BATTERY_LEVEL_TEMPLATE,
                CONF_CHARGING_TEMPLATE,
                CONF_CLEANING_TEMPLATE,
                CONF_DOCKED_TEMPLATE,
                CONF_ERROR_TEMPLATE,
                CONF_FAN_SPEED_TEMPLATE,
            )
            if key in config
        }

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT message."""
            if (
                msg.topic == self._state_topics[CONF_BATTERY_LEVEL_TOPIC]
                and CONF_BATTERY_LEVEL_TEMPLATE in self._config
            ):
                battery_level = self._templates[CONF_BATTERY_LEVEL_TEMPLATE](
                    msg.payload, PayloadSentinel.DEFAULT
                )
                if battery_level and battery_level is not PayloadSentinel.DEFAULT:
                    self._attr_battery_level = max(0, min(100, int(battery_level)))

            if (
                msg.topic == self._state_topics[CONF_CHARGING_TOPIC]
                and CONF_CHARGING_TEMPLATE in self._templates
            ):
                charging = self._templates[CONF_CHARGING_TEMPLATE](
                    msg.payload, PayloadSentinel.DEFAULT
                )
                if charging and charging is not PayloadSentinel.DEFAULT:
                    self._charging = cv.boolean(charging)

            if (
                msg.topic == self._state_topics[CONF_CLEANING_TOPIC]
                and CONF_CLEANING_TEMPLATE in self._config
            ):
                cleaning = self._templates[CONF_CLEANING_TEMPLATE](
                    msg.payload, PayloadSentinel.DEFAULT
                )
                if cleaning and cleaning is not PayloadSentinel.DEFAULT:
                    self._attr_is_on = cv.boolean(cleaning)

            if (
                msg.topic == self._state_topics[CONF_DOCKED_TOPIC]
                and CONF_DOCKED_TEMPLATE in self._config
            ):
                docked = self._templates[CONF_DOCKED_TEMPLATE](
                    msg.payload, PayloadSentinel.DEFAULT
                )
                if docked and docked is not PayloadSentinel.DEFAULT:
                    self._docked = cv.boolean(docked)

            if (
                msg.topic == self._state_topics[CONF_ERROR_TOPIC]
                and CONF_ERROR_TEMPLATE in self._config
            ):
                error = self._templates[CONF_ERROR_TEMPLATE](
                    msg.payload, PayloadSentinel.DEFAULT
                )
                if error is not PayloadSentinel.DEFAULT:
                    self._error = cv.string(error)

            if self._docked:
                if self._charging:
                    self._attr_status = "Docked & Charging"
                else:
                    self._attr_status = "Docked"
            elif self.is_on:
                self._attr_status = "Cleaning"
            elif self._error:
                self._attr_status = f"Error: {self._error}"
            else:
                self._attr_status = "Stopped"

            if (
                msg.topic == self._state_topics[CONF_FAN_SPEED_TOPIC]
                and CONF_FAN_SPEED_TEMPLATE in self._config
            ):
                fan_speed = self._templates[CONF_FAN_SPEED_TEMPLATE](
                    msg.payload, PayloadSentinel.DEFAULT
                )
                if fan_speed and fan_speed is not PayloadSentinel.DEFAULT:
                    self._attr_fan_speed = str(fan_speed)

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        topics_list = {topic for topic in self._state_topics.values() if topic}
        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                f"topic{i}": {
                    "topic": topic,
                    "msg_callback": message_received,
                    "qos": self._qos,
                    "encoding": self._encoding,
                }
                for i, topic in enumerate(topics_list)
            },
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the vacuum cleaner.

        No need to check VacuumEntityFeature.BATTERY, this won't be called if
        battery_level is None.
        """
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self._charging
        )

    async def _async_publish_command(self, feature: VacuumEntityFeature) -> None:
        """Publish a command."""

        if self._command_topic is None:
            return

        await self.async_publish(
            self._command_topic,
            self._payloads[_COMMANDS[feature]["payload"]],
            qos=self._qos,
            retain=self._retain,
            encoding=self._encoding,
        )
        self._attr_status = _COMMANDS[feature]["status"]
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the vacuum on."""
        await self._async_publish_command(VacuumEntityFeature.TURN_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the vacuum off."""
        await self._async_publish_command(VacuumEntityFeature.TURN_OFF)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        await self._async_publish_command(VacuumEntityFeature.STOP)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        await self._async_publish_command(VacuumEntityFeature.CLEAN_SPOT)

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum (usually by playing a song)."""
        await self._async_publish_command(VacuumEntityFeature.LOCATE)

    async def async_start_pause(self, **kwargs: Any) -> None:
        """Start, pause or resume the cleaning task."""
        await self._async_publish_command(VacuumEntityFeature.PAUSE)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Tell the vacuum to return to its dock."""
        await self._async_publish_command(VacuumEntityFeature.RETURN_HOME)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if (
            self._set_fan_speed_topic is None
            or (self.supported_features & VacuumEntityFeature.FAN_SPEED == 0)
            or fan_speed not in self.fan_speed_list
        ):
            return None

        await self.async_publish(
            self._set_fan_speed_topic,
            fan_speed,
            self._qos,
            self._retain,
            self._encoding,
        )
        self._attr_status = f"Setting fan to {fan_speed}..."
        self.async_write_ha_state()

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
        if params:
            message: dict[str, Any] = {"command": command}
            message.update(params)
            message_payload = json_dumps(message)
        else:
            message_payload = command
        await self.async_publish(
            self._send_command_topic,
            message_payload,
            self._qos,
            self._retain,
            self._encoding,
        )
        self._attr_status = f"Sending command {message_payload}..."
        self.async_write_ha_state()
