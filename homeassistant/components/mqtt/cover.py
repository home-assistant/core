"""Support for MQTT cover devices."""
from __future__ import annotations

from contextlib import suppress
import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import cover
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASSES_SCHEMA,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_VALUE_TEMPLATE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    DEFAULT_OPTIMISTIC,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
    warn_for_legacy_schema,
)
from .models import MqttCommandTemplate, MqttValueTemplate, ReceiveMessage
from .util import get_mqtt_data, valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_GET_POSITION_TOPIC = "position_topic"
CONF_GET_POSITION_TEMPLATE = "position_template"
CONF_SET_POSITION_TOPIC = "set_position_topic"
CONF_SET_POSITION_TEMPLATE = "set_position_template"
CONF_TILT_COMMAND_TOPIC = "tilt_command_topic"
CONF_TILT_COMMAND_TEMPLATE = "tilt_command_template"
CONF_TILT_STATUS_TOPIC = "tilt_status_topic"
CONF_TILT_STATUS_TEMPLATE = "tilt_status_template"

CONF_PAYLOAD_CLOSE = "payload_close"
CONF_PAYLOAD_OPEN = "payload_open"
CONF_PAYLOAD_STOP = "payload_stop"
CONF_POSITION_CLOSED = "position_closed"
CONF_POSITION_OPEN = "position_open"
CONF_STATE_CLOSED = "state_closed"
CONF_STATE_CLOSING = "state_closing"
CONF_STATE_OPEN = "state_open"
CONF_STATE_OPENING = "state_opening"
CONF_STATE_STOPPED = "state_stopped"
CONF_TILT_CLOSED_POSITION = "tilt_closed_value"
CONF_TILT_MAX = "tilt_max"
CONF_TILT_MIN = "tilt_min"
CONF_TILT_OPEN_POSITION = "tilt_opened_value"
CONF_TILT_STATE_OPTIMISTIC = "tilt_optimistic"

TILT_PAYLOAD = "tilt"
COVER_PAYLOAD = "cover"

DEFAULT_NAME = "MQTT Cover"
DEFAULT_PAYLOAD_CLOSE = "CLOSE"
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_PAYLOAD_STOP = "STOP"
DEFAULT_POSITION_CLOSED = 0
DEFAULT_POSITION_OPEN = 100
DEFAULT_RETAIN = False
DEFAULT_STATE_STOPPED = "stopped"
DEFAULT_TILT_CLOSED_POSITION = 0
DEFAULT_TILT_MAX = 100
DEFAULT_TILT_MIN = 0
DEFAULT_TILT_OPEN_POSITION = 100
DEFAULT_TILT_OPTIMISTIC = False

TILT_FEATURES = (
    CoverEntityFeature.OPEN_TILT
    | CoverEntityFeature.CLOSE_TILT
    | CoverEntityFeature.STOP_TILT
    | CoverEntityFeature.SET_TILT_POSITION
)

MQTT_COVER_ATTRIBUTES_BLOCKED = frozenset(
    {
        cover.ATTR_CURRENT_POSITION,
        cover.ATTR_CURRENT_TILT_POSITION,
    }
)


def validate_options(config: ConfigType) -> ConfigType:
    """Validate options.

    If set position topic is set then get position topic is set as well.
    """
    if CONF_SET_POSITION_TOPIC in config and CONF_GET_POSITION_TOPIC not in config:
        raise vol.Invalid(
            f"'{CONF_SET_POSITION_TOPIC}' must be set together with"
            f" '{CONF_GET_POSITION_TOPIC}'."
        )

    # if templates are set make sure the topic for the template is also set

    if CONF_VALUE_TEMPLATE in config and CONF_STATE_TOPIC not in config:
        raise vol.Invalid(
            f"'{CONF_VALUE_TEMPLATE}' must be set together with '{CONF_STATE_TOPIC}'."
        )

    if CONF_GET_POSITION_TEMPLATE in config and CONF_GET_POSITION_TOPIC not in config:
        raise vol.Invalid(
            f"'{CONF_GET_POSITION_TEMPLATE}' must be set together with"
            f" '{CONF_GET_POSITION_TOPIC}'."
        )

    if CONF_SET_POSITION_TEMPLATE in config and CONF_SET_POSITION_TOPIC not in config:
        raise vol.Invalid(
            f"'{CONF_SET_POSITION_TEMPLATE}' must be set together with"
            f" '{CONF_SET_POSITION_TOPIC}'."
        )

    if CONF_TILT_COMMAND_TEMPLATE in config and CONF_TILT_COMMAND_TOPIC not in config:
        raise vol.Invalid(
            f"'{CONF_TILT_COMMAND_TEMPLATE}' must be set together with"
            f" '{CONF_TILT_COMMAND_TOPIC}'."
        )

    if CONF_TILT_STATUS_TEMPLATE in config and CONF_TILT_STATUS_TOPIC not in config:
        raise vol.Invalid(
            f"'{CONF_TILT_STATUS_TEMPLATE}' must be set together with"
            f" '{CONF_TILT_STATUS_TOPIC}'."
        )

    return config


_PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_DEVICE_CLASS): vol.Any(DEVICE_CLASSES_SCHEMA, None),
        vol.Optional(CONF_GET_POSITION_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_CLOSE, default=DEFAULT_PAYLOAD_CLOSE): vol.Any(
            cv.string, None
        ),
        vol.Optional(CONF_PAYLOAD_OPEN, default=DEFAULT_PAYLOAD_OPEN): vol.Any(
            cv.string, None
        ),
        vol.Optional(CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP): vol.Any(
            cv.string, None
        ),
        vol.Optional(CONF_POSITION_CLOSED, default=DEFAULT_POSITION_CLOSED): int,
        vol.Optional(CONF_POSITION_OPEN, default=DEFAULT_POSITION_OPEN): int,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_SET_POSITION_TEMPLATE): cv.template,
        vol.Optional(CONF_SET_POSITION_TOPIC): valid_publish_topic,
        vol.Optional(CONF_STATE_CLOSED, default=STATE_CLOSED): cv.string,
        vol.Optional(CONF_STATE_CLOSING, default=STATE_CLOSING): cv.string,
        vol.Optional(CONF_STATE_OPEN, default=STATE_OPEN): cv.string,
        vol.Optional(CONF_STATE_OPENING, default=STATE_OPENING): cv.string,
        vol.Optional(CONF_STATE_STOPPED, default=DEFAULT_STATE_STOPPED): cv.string,
        vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(
            CONF_TILT_CLOSED_POSITION, default=DEFAULT_TILT_CLOSED_POSITION
        ): int,
        vol.Optional(CONF_TILT_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_TILT_MAX, default=DEFAULT_TILT_MAX): int,
        vol.Optional(CONF_TILT_MIN, default=DEFAULT_TILT_MIN): int,
        vol.Optional(CONF_TILT_OPEN_POSITION, default=DEFAULT_TILT_OPEN_POSITION): int,
        vol.Optional(
            CONF_TILT_STATE_OPTIMISTIC, default=DEFAULT_TILT_OPTIMISTIC
        ): cv.boolean,
        vol.Optional(CONF_TILT_STATUS_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_TILT_STATUS_TEMPLATE): cv.template,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_GET_POSITION_TEMPLATE): cv.template,
        vol.Optional(CONF_TILT_COMMAND_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(
    cv.removed("tilt_invert_state"),
    _PLATFORM_SCHEMA_BASE,
    validate_options,
)

# Configuring MQTT Covers under the cover platform key was deprecated in HA Core 2022.6
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA = vol.All(
    warn_for_legacy_schema(cover.DOMAIN),
)

DISCOVERY_SCHEMA = vol.All(
    cv.removed("tilt_invert_state"),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    validate_options,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT cover through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, cover.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT Cover."""
    async_add_entities([MqttCover(hass, config, config_entry, discovery_data)])


class MqttCover(MqttEntity, CoverEntity):
    """Representation of a cover that can be controlled using MQTT."""

    _entity_id_format: str = cover.ENTITY_ID_FORMAT
    _attributes_extra_blocked: frozenset[str] = MQTT_COVER_ATTRIBUTES_BLOCKED

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the cover."""
        self._position: int | None = None
        self._state: str | None = None

        self._optimistic: bool | None = None
        self._tilt_value: int | None = None
        self._tilt_optimistic: bool | None = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        no_position = (
            config.get(CONF_SET_POSITION_TOPIC) is None
            and config.get(CONF_GET_POSITION_TOPIC) is None
        )
        no_state = (
            config.get(CONF_COMMAND_TOPIC) is None
            and config.get(CONF_STATE_TOPIC) is None
        )
        no_tilt = (
            config.get(CONF_TILT_COMMAND_TOPIC) is None
            and config.get(CONF_TILT_STATUS_TOPIC) is None
        )
        optimistic_position = (
            config.get(CONF_SET_POSITION_TOPIC) is not None
            and config.get(CONF_GET_POSITION_TOPIC) is None
        )
        optimistic_state = (
            config.get(CONF_COMMAND_TOPIC) is not None
            and config.get(CONF_STATE_TOPIC) is None
        )
        optimistic_tilt = (
            config.get(CONF_TILT_COMMAND_TOPIC) is not None
            and config.get(CONF_TILT_STATUS_TOPIC) is None
        )

        if config[CONF_OPTIMISTIC] or (
            (no_position or optimistic_position)
            and (no_state or optimistic_state)
            and (no_tilt or optimistic_tilt)
        ):
            # Force into optimistic mode.
            self._optimistic = True

        if (
            config[CONF_TILT_STATE_OPTIMISTIC]
            or config.get(CONF_TILT_STATUS_TOPIC) is None
        ):
            # Force into optimistic tilt mode.
            self._tilt_optimistic = True

        template_config_attributes = {
            "position_open": self._config[CONF_POSITION_OPEN],
            "position_closed": self._config[CONF_POSITION_CLOSED],
            "tilt_min": self._config[CONF_TILT_MIN],
            "tilt_max": self._config[CONF_TILT_MAX],
        }

        self._value_template = MqttValueTemplate(
            self._config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value

        self._set_position_template = MqttCommandTemplate(
            self._config.get(CONF_SET_POSITION_TEMPLATE), entity=self
        ).async_render

        self._get_position_template = MqttValueTemplate(
            self._config.get(CONF_GET_POSITION_TEMPLATE),
            entity=self,
            config_attributes=template_config_attributes,
        ).async_render_with_possible_json_value

        self._set_tilt_template = MqttCommandTemplate(
            self._config.get(CONF_TILT_COMMAND_TEMPLATE), entity=self
        ).async_render

        self._tilt_status_template = MqttValueTemplate(
            self._config.get(CONF_TILT_STATUS_TEMPLATE),
            entity=self,
            config_attributes=template_config_attributes,
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        topics = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def tilt_message_received(msg: ReceiveMessage) -> None:
            """Handle tilt updates."""
            payload = self._tilt_status_template(msg.payload)

            if not payload:
                _LOGGER.debug("Ignoring empty tilt message from '%s'", msg.topic)
                return

            self.tilt_payload_received(payload)

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            payload = self._value_template(msg.payload)

            if not payload:
                _LOGGER.debug("Ignoring empty state message from '%s'", msg.topic)
                return

            if payload == self._config[CONF_STATE_STOPPED]:
                if self._config.get(CONF_GET_POSITION_TOPIC) is not None:
                    self._state = (
                        STATE_CLOSED
                        if self._position == DEFAULT_POSITION_CLOSED
                        else STATE_OPEN
                    )
                else:
                    self._state = (
                        STATE_CLOSED if self._state == STATE_CLOSING else STATE_OPEN
                    )
            elif payload == self._config[CONF_STATE_OPENING]:
                self._state = STATE_OPENING
            elif payload == self._config[CONF_STATE_CLOSING]:
                self._state = STATE_CLOSING
            elif payload == self._config[CONF_STATE_OPEN]:
                self._state = STATE_OPEN
            elif payload == self._config[CONF_STATE_CLOSED]:
                self._state = STATE_CLOSED
            else:
                _LOGGER.warning(
                    (
                        "Payload is not supported (e.g. open, closed, opening, closing,"
                        " stopped): %s"
                    ),
                    payload,
                )
                return

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        @callback
        @log_messages(self.hass, self.entity_id)
        def position_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT position messages."""
            payload: ReceivePayloadType = self._get_position_template(msg.payload)
            payload_dict: Any = None

            if not payload:
                _LOGGER.debug("Ignoring empty position message from '%s'", msg.topic)
                return

            with suppress(*JSON_DECODE_EXCEPTIONS):
                payload_dict = json_loads(payload)

            if payload_dict and isinstance(payload_dict, dict):
                if "position" not in payload_dict:
                    _LOGGER.warning(
                        "Template (position_template) returned JSON without position"
                        " attribute"
                    )
                    return
                if "tilt_position" in payload_dict:
                    if not self._config.get(CONF_TILT_STATE_OPTIMISTIC):
                        # reset forced set tilt optimistic
                        self._tilt_optimistic = False
                    self.tilt_payload_received(payload_dict["tilt_position"])
                payload = payload_dict["position"]

            try:
                percentage_payload = self.find_percentage_in_range(
                    float(payload), COVER_PAYLOAD
                )
            except ValueError:
                _LOGGER.warning("Payload '%s' is not numeric", payload)
                return

            self._position = percentage_payload
            if self._config.get(CONF_STATE_TOPIC) is None:
                self._state = (
                    STATE_CLOSED
                    if percentage_payload == DEFAULT_POSITION_CLOSED
                    else STATE_OPEN
                )

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._config.get(CONF_GET_POSITION_TOPIC):
            topics["get_position_topic"] = {
                "topic": self._config.get(CONF_GET_POSITION_TOPIC),
                "msg_callback": position_message_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }

        if self._config.get(CONF_STATE_TOPIC):
            topics["state_topic"] = {
                "topic": self._config.get(CONF_STATE_TOPIC),
                "msg_callback": state_message_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }

        if self._config.get(CONF_TILT_STATUS_TOPIC) is not None:
            topics["tilt_status_topic"] = {
                "topic": self._config.get(CONF_TILT_STATUS_TOPIC),
                "msg_callback": tilt_message_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return bool(self._optimistic)

    @property
    def is_closed(self) -> bool | None:
        """Return true if the cover is closed or None if the status is unknown."""
        if self._state is None:
            return None

        return self._state == STATE_CLOSED

    @property
    def is_opening(self) -> bool:
        """Return true if the cover is actively opening."""
        return self._state == STATE_OPENING

    @property
    def is_closing(self) -> bool:
        """Return true if the cover is actively closing."""
        return self._state == STATE_CLOSING

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt."""
        return self._tilt_value

    @property
    def device_class(self) -> CoverDeviceClass | None:
        """Return the class of this sensor."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        supported_features = CoverEntityFeature(0)
        if self._config.get(CONF_COMMAND_TOPIC) is not None:
            if self._config.get(CONF_PAYLOAD_OPEN) is not None:
                supported_features |= CoverEntityFeature.OPEN
            if self._config.get(CONF_PAYLOAD_CLOSE) is not None:
                supported_features |= CoverEntityFeature.CLOSE
            if self._config.get(CONF_PAYLOAD_STOP) is not None:
                supported_features |= CoverEntityFeature.STOP

        if self._config.get(CONF_SET_POSITION_TOPIC) is not None:
            supported_features |= CoverEntityFeature.SET_POSITION

        if self._config.get(CONF_TILT_COMMAND_TOPIC) is not None:
            supported_features |= TILT_FEATURES

        return supported_features

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up.

        This method is a coroutine.
        """
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_OPEN],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = STATE_OPEN
            if self._config.get(CONF_GET_POSITION_TOPIC):
                self._position = self.find_percentage_in_range(
                    self._config[CONF_POSITION_OPEN], COVER_PAYLOAD
                )
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down.

        This method is a coroutine.
        """
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_CLOSE],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._state = STATE_CLOSED
            if self._config.get(CONF_GET_POSITION_TOPIC):
                self._position = self.find_percentage_in_range(
                    self._config[CONF_POSITION_CLOSED], COVER_PAYLOAD
                )
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device.

        This method is a coroutine.
        """
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_STOP],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover open."""
        tilt_open_position = self._config[CONF_TILT_OPEN_POSITION]
        variables = {
            "tilt_position": tilt_open_position,
            "entity_id": self.entity_id,
            "position_open": self._config.get(CONF_POSITION_OPEN),
            "position_closed": self._config.get(CONF_POSITION_CLOSED),
            "tilt_min": self._config.get(CONF_TILT_MIN),
            "tilt_max": self._config.get(CONF_TILT_MAX),
        }
        tilt_payload = self._set_tilt_template(tilt_open_position, variables=variables)
        await self.async_publish(
            self._config[CONF_TILT_COMMAND_TOPIC],
            tilt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._tilt_optimistic:
            self._tilt_value = self.find_percentage_in_range(
                float(self._config[CONF_TILT_OPEN_POSITION])
            )
            self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover closed."""
        tilt_closed_position = self._config[CONF_TILT_CLOSED_POSITION]
        variables = {
            "tilt_position": tilt_closed_position,
            "entity_id": self.entity_id,
            "position_open": self._config.get(CONF_POSITION_OPEN),
            "position_closed": self._config.get(CONF_POSITION_CLOSED),
            "tilt_min": self._config.get(CONF_TILT_MIN),
            "tilt_max": self._config.get(CONF_TILT_MAX),
        }
        tilt_payload = self._set_tilt_template(
            tilt_closed_position, variables=variables
        )
        await self.async_publish(
            self._config[CONF_TILT_COMMAND_TOPIC],
            tilt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._tilt_optimistic:
            self._tilt_value = self.find_percentage_in_range(
                float(self._config[CONF_TILT_CLOSED_POSITION])
            )
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt = kwargs[ATTR_TILT_POSITION]
        percentage_tilt = tilt
        tilt = self.find_in_range_from_percent(tilt)
        # Handover the tilt after calculated from percent would make it more
        # consistent with receiving templates
        variables = {
            "tilt_position": percentage_tilt,
            "entity_id": self.entity_id,
            "position_open": self._config.get(CONF_POSITION_OPEN),
            "position_closed": self._config.get(CONF_POSITION_CLOSED),
            "tilt_min": self._config.get(CONF_TILT_MIN),
            "tilt_max": self._config.get(CONF_TILT_MAX),
        }
        tilt = self._set_tilt_template(tilt, variables=variables)

        await self.async_publish(
            self._config[CONF_TILT_COMMAND_TOPIC],
            tilt,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._tilt_optimistic:
            _LOGGER.debug("Set tilt value optimistic")
            self._tilt_value = percentage_tilt
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        percentage_position = position
        position = self.find_in_range_from_percent(position, COVER_PAYLOAD)
        variables = {
            "position": percentage_position,
            "entity_id": self.entity_id,
            "position_open": self._config[CONF_POSITION_OPEN],
            "position_closed": self._config[CONF_POSITION_CLOSED],
            "tilt_min": self._config[CONF_TILT_MIN],
            "tilt_max": self._config[CONF_TILT_MAX],
        }
        position = self._set_position_template(position, variables=variables)

        await self.async_publish(
            self._config[CONF_SET_POSITION_TOPIC],
            position,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            self._state = (
                STATE_CLOSED
                if percentage_position == self._config[CONF_POSITION_CLOSED]
                else STATE_OPEN
            )
            self._position = percentage_position
            self.async_write_ha_state()

    async def async_toggle_tilt(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if self.is_tilt_closed():
            await self.async_open_cover_tilt(**kwargs)
        else:
            await self.async_close_cover_tilt(**kwargs)

    def is_tilt_closed(self) -> bool:
        """Return if the cover is tilted closed."""
        return self._tilt_value == self.find_percentage_in_range(
            float(self._config[CONF_TILT_CLOSED_POSITION])
        )

    def find_percentage_in_range(
        self, position: float, range_type: str = TILT_PAYLOAD
    ) -> int:
        """Find the 0-100% value within the specified range."""
        # the range of motion as defined by the min max values
        if range_type == COVER_PAYLOAD:
            max_range: int = self._config[CONF_POSITION_OPEN]
            min_range: int = self._config[CONF_POSITION_CLOSED]
        else:
            max_range = self._config[CONF_TILT_MAX]
            min_range = self._config[CONF_TILT_MIN]
        current_range = max_range - min_range
        # offset to be zero based
        offset_position = position - min_range
        position_percentage = round(float(offset_position) / current_range * 100.0)

        max_percent = 100
        min_percent = 0
        position_percentage = min(max(position_percentage, min_percent), max_percent)

        return position_percentage

    def find_in_range_from_percent(
        self, percentage: float, range_type: str = TILT_PAYLOAD
    ) -> int:
        """Find the adjusted value for 0-100% within the specified range.

        if the range is 80-180 and the percentage is 90
        this method would determine the value to send on the topic
        by offsetting the max and min, getting the percentage value and
        returning the offset
        """
        if range_type == COVER_PAYLOAD:
            max_range: int = self._config[CONF_POSITION_OPEN]
            min_range: int = self._config[CONF_POSITION_CLOSED]
        else:
            max_range = self._config[CONF_TILT_MAX]
            min_range = self._config[CONF_TILT_MIN]
        offset = min_range
        current_range = max_range - min_range
        position = round(current_range * (percentage / 100.0))
        position += offset

        return position

    @callback
    def tilt_payload_received(self, _payload: Any) -> None:
        """Set the tilt value."""

        try:
            payload = int(round(float(_payload)))
        except ValueError:
            _LOGGER.warning("Payload '%s' is not numeric", _payload)
            return

        if (
            self._config[CONF_TILT_MIN] <= int(payload) <= self._config[CONF_TILT_MAX]
            or self._config[CONF_TILT_MAX]
            <= int(payload)
            <= self._config[CONF_TILT_MIN]
        ):
            level = self.find_percentage_in_range(payload)
            self._tilt_value = level
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)
        else:
            _LOGGER.warning(
                "Payload '%s' is out of range, must be between '%s' and '%s' inclusive",
                payload,
                self._config[CONF_TILT_MIN],
                self._config[CONF_TILT_MAX],
            )
