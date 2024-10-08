"""Support for MQTT cover devices."""

from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import cover
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASSES_SCHEMA,
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
from homeassistant.helpers.typing import ConfigType, VolSchemaType
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import (
    CONF_COMMAND_TOPIC,
    CONF_PAYLOAD_CLOSE,
    CONF_PAYLOAD_OPEN,
    CONF_PAYLOAD_STOP,
    CONF_POSITION_CLOSED,
    CONF_POSITION_OPEN,
    CONF_RETAIN,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATE_TOPIC,
    DEFAULT_OPTIMISTIC,
    DEFAULT_PAYLOAD_CLOSE,
    DEFAULT_PAYLOAD_OPEN,
    DEFAULT_POSITION_CLOSED,
    DEFAULT_POSITION_OPEN,
    DEFAULT_RETAIN,
    PAYLOAD_NONE,
)
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import MqttCommandTemplate, MqttValueTemplate, ReceiveMessage
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_GET_POSITION_TOPIC = "position_topic"
CONF_GET_POSITION_TEMPLATE = "position_template"
CONF_SET_POSITION_TOPIC = "set_position_topic"
CONF_SET_POSITION_TEMPLATE = "set_position_template"
CONF_TILT_COMMAND_TOPIC = "tilt_command_topic"
CONF_TILT_COMMAND_TEMPLATE = "tilt_command_template"
CONF_TILT_STATUS_TOPIC = "tilt_status_topic"
CONF_TILT_STATUS_TEMPLATE = "tilt_status_template"

CONF_STATE_STOPPED = "state_stopped"
CONF_TILT_CLOSED_POSITION = "tilt_closed_value"
CONF_TILT_MAX = "tilt_max"
CONF_TILT_MIN = "tilt_min"
CONF_TILT_OPEN_POSITION = "tilt_opened_value"
CONF_TILT_STATE_OPTIMISTIC = "tilt_optimistic"

TILT_PAYLOAD = "tilt"
COVER_PAYLOAD = "cover"

DEFAULT_NAME = "MQTT Cover"

DEFAULT_STATE_STOPPED = "stopped"
DEFAULT_PAYLOAD_STOP = "STOP"

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
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
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
    _PLATFORM_SCHEMA_BASE,
    validate_options,
)

DISCOVERY_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    validate_options,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT cover through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttCover,
        cover.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttCover(MqttEntity, CoverEntity):
    """Representation of a cover that can be controlled using MQTT."""

    _attr_is_closed: bool | None = None
    _attributes_extra_blocked: frozenset[str] = MQTT_COVER_ATTRIBUTES_BLOCKED
    _default_name = DEFAULT_NAME
    _entity_id_format: str = cover.ENTITY_ID_FORMAT
    _optimistic: bool
    _tilt_optimistic: bool
    _tilt_closed_percentage: int
    _tilt_open_percentage: int
    _pos_range: tuple[int, int]
    _tilt_range: tuple[int, int]

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """Set up cover from config."""
        self._pos_range = (config[CONF_POSITION_CLOSED] + 1, config[CONF_POSITION_OPEN])
        self._tilt_range = (config[CONF_TILT_MIN] + 1, config[CONF_TILT_MAX])
        self._tilt_closed_percentage = ranged_value_to_percentage(
            self._tilt_range, config[CONF_TILT_CLOSED_POSITION]
        )
        self._tilt_open_percentage = ranged_value_to_percentage(
            self._tilt_range, config[CONF_TILT_OPEN_POSITION]
        )
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

        self._optimistic = config[CONF_OPTIMISTIC] or (
            (no_position or optimistic_position)
            and (no_state or optimistic_state)
            and (no_tilt or optimistic_tilt)
        )
        self._attr_assumed_state = self._optimistic

        self._tilt_optimistic = (
            config[CONF_TILT_STATE_OPTIMISTIC]
            or config.get(CONF_TILT_STATUS_TOPIC) is None
        )

        template_config_attributes = {
            "position_open": config[CONF_POSITION_OPEN],
            "position_closed": config[CONF_POSITION_CLOSED],
            "tilt_min": config[CONF_TILT_MIN],
            "tilt_max": config[CONF_TILT_MAX],
        }

        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value

        self._set_position_template = MqttCommandTemplate(
            config.get(CONF_SET_POSITION_TEMPLATE), entity=self
        ).async_render

        self._get_position_template = MqttValueTemplate(
            config.get(CONF_GET_POSITION_TEMPLATE),
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

        self._attr_device_class = self._config.get(CONF_DEVICE_CLASS)

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

        self._attr_supported_features = supported_features

    @callback
    def _update_state(self, state: str | None) -> None:
        """Update the cover state."""
        if state is None:
            # Reset the state to `unknown`
            self._attr_is_closed = None
        else:
            self._attr_is_closed = state == STATE_CLOSED
        self._attr_is_opening = state == STATE_OPENING
        self._attr_is_closing = state == STATE_CLOSING

    @callback
    def _tilt_message_received(self, msg: ReceiveMessage) -> None:
        """Handle tilt updates."""
        payload = self._tilt_status_template(msg.payload)

        if not payload:
            _LOGGER.debug("Ignoring empty tilt message from '%s'", msg.topic)
            return

        self.tilt_payload_received(payload)

    @callback
    def _state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle new MQTT state messages."""
        payload = self._value_template(msg.payload)

        if not payload:
            _LOGGER.debug("Ignoring empty state message from '%s'", msg.topic)
            return

        state: str | None
        if payload == self._config[CONF_STATE_STOPPED]:
            if self._config.get(CONF_GET_POSITION_TOPIC) is not None:
                state = (
                    STATE_CLOSED
                    if self._attr_current_cover_position == DEFAULT_POSITION_CLOSED
                    else STATE_OPEN
                )
            else:
                state = (
                    STATE_CLOSED
                    if self.state in [STATE_CLOSED, STATE_CLOSING]
                    else STATE_OPEN
                )
        elif payload == self._config[CONF_STATE_OPENING]:
            state = STATE_OPENING
        elif payload == self._config[CONF_STATE_CLOSING]:
            state = STATE_CLOSING
        elif payload == self._config[CONF_STATE_OPEN]:
            state = STATE_OPEN
        elif payload == self._config[CONF_STATE_CLOSED]:
            state = STATE_CLOSED
        elif payload == PAYLOAD_NONE:
            state = None
        else:
            _LOGGER.warning(
                (
                    "Payload is not supported (e.g. open, closed, opening, closing,"
                    " stopped): %s"
                ),
                payload,
            )
            return
        self._update_state(state)

    @callback
    def _position_message_received(self, msg: ReceiveMessage) -> None:
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
            percentage_payload = ranged_value_to_percentage(
                self._pos_range, float(payload)
            )
        except ValueError:
            _LOGGER.warning("Payload '%s' is not numeric", payload)
            return

        self._attr_current_cover_position = min(100, max(0, percentage_payload))
        if self._config.get(CONF_STATE_TOPIC) is None:
            self._update_state(
                STATE_CLOSED if self.current_cover_position == 0 else STATE_OPEN
            )

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_GET_POSITION_TOPIC,
            self._position_message_received,
            {
                "_attr_current_cover_position",
                "_attr_current_cover_tilt_position",
                "_attr_is_closed",
                "_attr_is_closing",
                "_attr_is_opening",
            },
        )
        self.add_subscription(
            CONF_STATE_TOPIC,
            self._state_message_received,
            {"_attr_is_closed", "_attr_is_closing", "_attr_is_opening"},
        )
        self.add_subscription(
            CONF_TILT_STATUS_TOPIC,
            self._tilt_message_received,
            {"_attr_current_cover_tilt_position"},
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up.

        This method is a coroutine.
        """
        await self.async_publish_with_config(
            self._config[CONF_COMMAND_TOPIC], self._config[CONF_PAYLOAD_OPEN]
        )
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._update_state(STATE_OPEN)
            if self._config.get(CONF_GET_POSITION_TOPIC):
                self._attr_current_cover_position = 100
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down.

        This method is a coroutine.
        """
        await self.async_publish_with_config(
            self._config[CONF_COMMAND_TOPIC], self._config[CONF_PAYLOAD_CLOSE]
        )
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._update_state(STATE_CLOSED)
            if self._config.get(CONF_GET_POSITION_TOPIC):
                self._attr_current_cover_position = 0
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device.

        This method is a coroutine.
        """
        await self.async_publish_with_config(
            self._config[CONF_COMMAND_TOPIC], self._config[CONF_PAYLOAD_STOP]
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
        await self.async_publish_with_config(
            self._config[CONF_TILT_COMMAND_TOPIC], tilt_payload
        )
        if self._tilt_optimistic:
            self._attr_current_cover_tilt_position = self._tilt_open_percentage
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
        await self.async_publish_with_config(
            self._config[CONF_TILT_COMMAND_TOPIC], tilt_payload
        )
        if self._tilt_optimistic:
            self._attr_current_cover_tilt_position = self._tilt_closed_percentage
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt_percentage = kwargs[ATTR_TILT_POSITION]
        tilt_ranged = round(
            percentage_to_ranged_value(self._tilt_range, tilt_percentage)
        )
        # Handover the tilt after calculated from percent would make it more
        # consistent with receiving templates
        variables = {
            "tilt_position": tilt_percentage,
            "entity_id": self.entity_id,
            "position_open": self._config.get(CONF_POSITION_OPEN),
            "position_closed": self._config.get(CONF_POSITION_CLOSED),
            "tilt_min": self._config.get(CONF_TILT_MIN),
            "tilt_max": self._config.get(CONF_TILT_MAX),
        }
        tilt_rendered = self._set_tilt_template(tilt_ranged, variables=variables)
        await self.async_publish_with_config(
            self._config[CONF_TILT_COMMAND_TOPIC], tilt_rendered
        )
        if self._tilt_optimistic:
            _LOGGER.debug("Set tilt value optimistic")
            self._attr_current_cover_tilt_position = tilt_percentage
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position_percentage = kwargs[ATTR_POSITION]
        position_ranged = round(
            percentage_to_ranged_value(self._pos_range, position_percentage)
        )
        variables = {
            "position": position_percentage,
            "entity_id": self.entity_id,
            "position_open": self._config[CONF_POSITION_OPEN],
            "position_closed": self._config[CONF_POSITION_CLOSED],
            "tilt_min": self._config[CONF_TILT_MIN],
            "tilt_max": self._config[CONF_TILT_MAX],
        }
        position_rendered = self._set_position_template(
            position_ranged, variables=variables
        )
        await self.async_publish_with_config(
            self._config[CONF_SET_POSITION_TOPIC], position_rendered
        )
        if self._optimistic:
            self._update_state(
                STATE_CLOSED
                if position_percentage <= self._config[CONF_POSITION_CLOSED]
                else STATE_OPEN
            )
            self._attr_current_cover_position = position_percentage
            self.async_write_ha_state()

    async def async_toggle_tilt(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if (
            self.current_cover_tilt_position is not None
            and self.current_cover_tilt_position <= self._tilt_closed_percentage
        ):
            await self.async_open_cover_tilt(**kwargs)
        else:
            await self.async_close_cover_tilt(**kwargs)

    @callback
    def tilt_payload_received(self, _payload: Any) -> None:
        """Set the tilt value."""

        try:
            payload = round(float(_payload))
        except ValueError:
            _LOGGER.warning("Payload '%s' is not numeric", _payload)
            return

        if (
            self._config[CONF_TILT_MIN] <= payload <= self._config[CONF_TILT_MAX]
            or self._config[CONF_TILT_MAX] <= payload <= self._config[CONF_TILT_MIN]
        ):
            level = ranged_value_to_percentage(self._tilt_range, payload)
            self._attr_current_cover_tilt_position = level
        else:
            _LOGGER.warning(
                "Payload '%s' is out of range, must be between '%s' and '%s' inclusive",
                payload,
                self._config[CONF_TILT_MIN],
                self._config[CONF_TILT_MAX],
            )
