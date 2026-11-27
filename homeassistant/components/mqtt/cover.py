"""Support for MQTT cover devices."""

from contextlib import suppress
import logging
from typing import Any, override

import probatio

from homeassistant.components import cover
from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA,
    CoverEntity,
    CoverEntityCapabilityAttribute,
    CoverEntityFeature,
    CoverEntityStateAttribute,
    CoverServiceArgument,
    CoverState,
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
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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
    ATTR_DISCOVERY_TOPIC,
    CONF_COMMAND_TOPIC,
    CONF_GET_POSITION_TEMPLATE,
    CONF_GET_POSITION_TOPIC,
    CONF_PAYLOAD_CLOSE,
    CONF_PAYLOAD_OPEN,
    CONF_PAYLOAD_STOP,
    CONF_PAYLOAD_STOP_TILT,
    CONF_POSITION_CLOSED,
    CONF_POSITION_OPEN,
    CONF_RETAIN,
    CONF_SET_POSITION_TEMPLATE,
    CONF_SET_POSITION_TOPIC,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATE_STOPPED,
    CONF_STATE_TOPIC,
    CONF_TILT_CLOSED_POSITION,
    CONF_TILT_COMMAND_TEMPLATE,
    CONF_TILT_COMMAND_TOPIC,
    CONF_TILT_MAX,
    CONF_TILT_MIN,
    CONF_TILT_OPEN_POSITION,
    CONF_TILT_STATE_OPTIMISTIC,
    CONF_TILT_STATUS_TEMPLATE,
    CONF_TILT_STATUS_TOPIC,
    DEFAULT_OPTIMISTIC,
    DEFAULT_PAYLOAD_CLOSE,
    DEFAULT_PAYLOAD_OPEN,
    DEFAULT_PAYLOAD_STOP,
    DEFAULT_POSITION_CLOSED,
    DEFAULT_POSITION_OPEN,
    DEFAULT_RETAIN,
    DEFAULT_STATE_STOPPED,
    DEFAULT_TILT_CLOSED_POSITION,
    DEFAULT_TILT_MAX,
    DEFAULT_TILT_MIN,
    DEFAULT_TILT_OPEN_POSITION,
    DEFAULT_TILT_OPTIMISTIC,
    DOMAIN,
    PAYLOAD_NONE,
)
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import MqttCommandTemplate, MqttValueTemplate, ReceiveMessage
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import learn_more_url, valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

CONF_CLOSED_TILT_POSITIONS = "closed_tilt_positions"
CONF_OPEN_TILT_POSITION = "open_tilt_position"
CONF_TILT_END_ANGLE = "tilt_end_angle"
CONF_TILT_START_ANGLE = "tilt_start_angle"

DEFAULT_NAME = "MQTT Cover"

DEPRECATED_TILT_VALUES_BREAKS_IN_HA_VERSION = "2027.7.0"

LEGACY_TILT_OPTIONS = (CONF_TILT_OPEN_POSITION, CONF_TILT_CLOSED_POSITION)
TILT_POSITION_OPTIONS = (
    CONF_TILT_START_ANGLE,
    CONF_TILT_END_ANGLE,
    CONF_OPEN_TILT_POSITION,
    CONF_CLOSED_TILT_POSITIONS,
)

TILT_FEATURES = (
    CoverEntityFeature.OPEN_TILT
    | CoverEntityFeature.CLOSE_TILT
    | CoverEntityFeature.STOP_TILT
    | CoverEntityFeature.SET_TILT_POSITION
)

MQTT_COVER_ATTRIBUTES_BLOCKED = frozenset(
    {
        CoverEntityStateAttribute.CURRENT_POSITION,
        CoverEntityStateAttribute.CURRENT_TILT_POSITION,
        CoverEntityCapabilityAttribute.OPEN_TILT_POSITION,
        CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS,
        CoverEntityCapabilityAttribute.TILT_START_ANGLE,
        CoverEntityCapabilityAttribute.TILT_END_ANGLE,
    }
)


def resolve_tilt_positions(config: ConfigType) -> tuple[int, list[int]]:
    """Return the open and closed tilt positions, as the cover entity derives them."""
    start: int | None = config.get(CONF_TILT_START_ANGLE)
    end: int | None = config.get(CONF_TILT_END_ANGLE)
    if (open_position := config.get(CONF_OPEN_TILT_POSITION)) is None:
        if start is None or end is None:
            open_position = 100
        else:
            open_position = min(max(round(-start * 100 / (end - start)), 0), 100)
    closed_positions: list[int] | None
    if (closed_positions := config.get(CONF_CLOSED_TILT_POSITIONS)) is None:
        if start is None or end is None:
            closed_positions = [100 if open_position == 0 else 0]
        else:
            flattest = max(abs(start), abs(end))
            closed_positions = [
                position
                for position, angle in ((0, start), (100, end))
                if abs(angle) == flattest
            ]
    return open_position, closed_positions


def validate_options(config: ConfigType) -> ConfigType:
    """Validate options.

    If set position topic is set then get position topic is set as well.
    """
    if CONF_SET_POSITION_TOPIC in config and CONF_GET_POSITION_TOPIC not in config:
        raise probatio.Invalid(
            f"'{CONF_SET_POSITION_TOPIC}' must be set together with"
            f" '{CONF_GET_POSITION_TOPIC}'."
        )

    # if templates are set make sure the topic for the template is also set

    if CONF_VALUE_TEMPLATE in config and CONF_STATE_TOPIC not in config:
        raise probatio.Invalid(
            f"'{CONF_VALUE_TEMPLATE}' must be set together with '{CONF_STATE_TOPIC}'."
        )

    if CONF_GET_POSITION_TEMPLATE in config and CONF_GET_POSITION_TOPIC not in config:
        raise probatio.Invalid(
            f"'{CONF_GET_POSITION_TEMPLATE}' must be set together with"
            f" '{CONF_GET_POSITION_TOPIC}'."
        )

    if CONF_SET_POSITION_TEMPLATE in config and CONF_SET_POSITION_TOPIC not in config:
        raise probatio.Invalid(
            f"'{CONF_SET_POSITION_TEMPLATE}' must be set together with"
            f" '{CONF_SET_POSITION_TOPIC}'."
        )

    if CONF_TILT_COMMAND_TEMPLATE in config and CONF_TILT_COMMAND_TOPIC not in config:
        raise probatio.Invalid(
            f"'{CONF_TILT_COMMAND_TEMPLATE}' must be set together with"
            f" '{CONF_TILT_COMMAND_TOPIC}'."
        )

    if CONF_TILT_STATUS_TEMPLATE in config and CONF_TILT_STATUS_TOPIC not in config:
        raise probatio.Invalid(
            f"'{CONF_TILT_STATUS_TEMPLATE}' must be set together with"
            f" '{CONF_TILT_STATUS_TOPIC}'."
        )

    if (CONF_TILT_START_ANGLE in config) != (CONF_TILT_END_ANGLE in config):
        raise probatio.Invalid(
            f"'{CONF_TILT_START_ANGLE}' must be set together with"
            f" '{CONF_TILT_END_ANGLE}'."
        )

    if (
        CONF_TILT_START_ANGLE in config
        and config[CONF_TILT_START_ANGLE] == config[CONF_TILT_END_ANGLE]
    ):
        raise probatio.Invalid(
            f"'{CONF_TILT_START_ANGLE}' and '{CONF_TILT_END_ANGLE}' must differ."
        )

    if any(option in config for option in LEGACY_TILT_OPTIONS) and any(
        option in config for option in TILT_POSITION_OPTIONS
    ):
        raise probatio.Invalid(
            f"'{CONF_TILT_OPEN_POSITION}' and '{CONF_TILT_CLOSED_POSITION}' cannot"
            f" be used together with '{CONF_TILT_START_ANGLE}',"
            f" '{CONF_TILT_END_ANGLE}', '{CONF_OPEN_TILT_POSITION}' or"
            f" '{CONF_CLOSED_TILT_POSITIONS}'."
        )

    open_position, closed_positions = resolve_tilt_positions(config)
    if open_position in closed_positions:
        raise probatio.Invalid(
            f"The open tilt position {open_position} must not be one of the closed"
            f" tilt positions {closed_positions}."
        )

    return config


_PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        probatio.Optional(CONF_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_DEVICE_CLASS): probatio.Any(DEVICE_CLASSES_SCHEMA, None),
        probatio.Optional(CONF_GET_POSITION_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_NAME): probatio.Any(cv.string, None),
        probatio.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        probatio.Optional(
            CONF_PAYLOAD_CLOSE, default=DEFAULT_PAYLOAD_CLOSE
        ): probatio.Any(cv.string, None),
        probatio.Optional(
            CONF_PAYLOAD_OPEN, default=DEFAULT_PAYLOAD_OPEN
        ): probatio.Any(cv.string, None),
        probatio.Optional(
            CONF_PAYLOAD_STOP, default=DEFAULT_PAYLOAD_STOP
        ): probatio.Any(cv.string, None),
        probatio.Optional(CONF_POSITION_CLOSED, default=DEFAULT_POSITION_CLOSED): int,
        probatio.Optional(CONF_POSITION_OPEN, default=DEFAULT_POSITION_OPEN): int,
        probatio.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        probatio.Optional(CONF_SET_POSITION_TEMPLATE): cv.template,
        probatio.Optional(CONF_SET_POSITION_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_STATE_CLOSED, default=STATE_CLOSED): cv.string,
        probatio.Optional(CONF_STATE_CLOSING, default=STATE_CLOSING): cv.string,
        probatio.Optional(CONF_STATE_OPEN, default=STATE_OPEN): cv.string,
        probatio.Optional(CONF_STATE_OPENING, default=STATE_OPENING): cv.string,
        probatio.Optional(CONF_STATE_STOPPED, default=DEFAULT_STATE_STOPPED): cv.string,
        probatio.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_TILT_CLOSED_POSITION): int,
        probatio.Optional(CONF_TILT_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_TILT_MAX, default=DEFAULT_TILT_MAX): int,
        probatio.Optional(CONF_TILT_MIN, default=DEFAULT_TILT_MIN): int,
        probatio.Optional(CONF_TILT_OPEN_POSITION): int,
        probatio.Optional(CONF_TILT_START_ANGLE): probatio.All(
            int, probatio.Range(min=-90, max=90)
        ),
        probatio.Optional(CONF_TILT_END_ANGLE): probatio.All(
            int, probatio.Range(min=-90, max=90)
        ),
        probatio.Optional(CONF_OPEN_TILT_POSITION): probatio.All(
            int, probatio.Range(min=0, max=100)
        ),
        probatio.Optional(CONF_CLOSED_TILT_POSITIONS): probatio.All(
            probatio.EnsureList(),
            [probatio.In([0, 100])],
            probatio.Length(min=1),
            probatio.Unique(),
            sorted,
        ),
        probatio.Optional(
            CONF_TILT_STATE_OPTIMISTIC, default=DEFAULT_TILT_OPTIMISTIC
        ): cv.boolean,
        probatio.Optional(CONF_TILT_STATUS_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_TILT_STATUS_TEMPLATE): cv.template,
        probatio.Optional(CONF_VALUE_TEMPLATE): cv.template,
        probatio.Optional(CONF_GET_POSITION_TEMPLATE): cv.template,
        probatio.Optional(CONF_TILT_COMMAND_TEMPLATE): cv.template,
        probatio.Optional(
            CONF_PAYLOAD_STOP_TILT, default=DEFAULT_PAYLOAD_STOP
        ): probatio.Any(cv.string, None),
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = probatio.All(
    _PLATFORM_SCHEMA_BASE,
    validate_options,
)

DISCOVERY_SCHEMA = probatio.All(
    _PLATFORM_SCHEMA_BASE.extend({}, extra=probatio.REMOVE_EXTRA),
    validate_options,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    _legacy_tilt: bool
    _deprecated_tilt_values: bool
    _tilt_closed_percentage: int
    _tilt_open_percentage: int
    _tilt_closed_positions: list[int]
    _pos_range: tuple[int, int]
    _tilt_range: tuple[int, int]

    @staticmethod
    @override
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    @override
    def _setup_from_config(self, config: ConfigType) -> None:
        """Set up cover from config."""
        self._pos_range = (config[CONF_POSITION_CLOSED] + 1, config[CONF_POSITION_OPEN])
        self._tilt_range = (config[CONF_TILT_MIN] + 1, config[CONF_TILT_MAX])
        self._setup_tilt_positions(config)
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

    def _setup_tilt_positions(self, config: ConfigType) -> None:
        """Set up the open and closed tilt positions and the tilt angles."""
        self._deprecated_tilt_values = any(
            option in config for option in LEGACY_TILT_OPTIONS
        )
        # Without the new options, keep sending the raw tilt values as before
        self._legacy_tilt = not any(
            option in config for option in TILT_POSITION_OPTIONS
        )
        if not self._legacy_tilt:
            self._tilt_open_percentage, self._tilt_closed_positions = (
                resolve_tilt_positions(config)
            )
            self._attr_open_tilt_position = config.get(CONF_OPEN_TILT_POSITION)
            self._attr_closed_tilt_positions = config.get(CONF_CLOSED_TILT_POSITIONS)
            self._attr_tilt_start_angle = config.get(CONF_TILT_START_ANGLE)
            self._attr_tilt_end_angle = config.get(CONF_TILT_END_ANGLE)
            return

        self._tilt_open_percentage = self._tilt_value_to_percentage(
            config.get(CONF_TILT_OPEN_POSITION, DEFAULT_TILT_OPEN_POSITION)
        )
        self._tilt_closed_percentage = self._tilt_value_to_percentage(
            config.get(CONF_TILT_CLOSED_POSITION, DEFAULT_TILT_CLOSED_POSITION)
        )
        # The cover entity only accepts closed tilt positions at the ends
        closed_at_end = self._tilt_closed_percentage in (0, 100)
        self._tilt_closed_positions = (
            [self._tilt_closed_percentage]
            if closed_at_end
            else [100 if self._tilt_open_percentage == 0 else 0]
        )
        consistent = self._tilt_open_percentage not in self._tilt_closed_positions
        self._attr_open_tilt_position = (
            self._tilt_open_percentage if consistent else None
        )
        self._attr_closed_tilt_positions = (
            self._tilt_closed_positions if consistent and closed_at_end else None
        )
        self._attr_tilt_start_angle = None
        self._attr_tilt_end_angle = None

    def _tilt_value_to_percentage(self, value: int) -> int:
        """Convert a tilt value of the device to a percentage from 0 to 100."""
        return min(max(ranged_value_to_percentage(self._tilt_range, value), 0), 100)

    @override
    async def mqtt_async_added_to_hass(self) -> None:
        """Report the use of the deprecated tilt options."""
        if (discovery_data := self._discovery_data) is not None:
            if self._deprecated_tilt_values:
                _LOGGER.warning(
                    "The MQTT cover %s, discovered on topic %s, uses the deprecated"
                    " '%s' or '%s' option, which will stop working in Home"
                    " Assistant %s. Update the discovery payload to use '%s' and"
                    " '%s', or '%s' and '%s' instead",
                    self.entity_id,
                    discovery_data[ATTR_DISCOVERY_TOPIC],
                    CONF_TILT_OPEN_POSITION,
                    CONF_TILT_CLOSED_POSITION,
                    DEPRECATED_TILT_VALUES_BREAKS_IN_HA_VERSION,
                    CONF_TILT_START_ANGLE,
                    CONF_TILT_END_ANGLE,
                    CONF_OPEN_TILT_POSITION,
                    CONF_CLOSED_TILT_POSITIONS,
                )
            return
        # Subentries still store the legacy options until the UI is migrated
        if (
            self.registry_entry is not None
            and self.registry_entry.config_subentry_id is not None
        ):
            return
        issue_id = f"deprecated_tilt_values_{self.entity_id}"
        if not self._deprecated_tilt_values:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version=DEPRECATED_TILT_VALUES_BREAKS_IN_HA_VERSION,
            is_fixable=False,
            issue_domain=cover.DOMAIN,
            learn_more_url=learn_more_url(cover.DOMAIN),
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_tilt_values",
            translation_placeholders={
                "entity_id": self.entity_id,
                "breaks_in_ha_version": DEPRECATED_TILT_VALUES_BREAKS_IN_HA_VERSION,
            },
        )

    @callback
    def _update_state(self, state: str | None) -> None:
        """Update the cover state."""
        if state is None:
            # Reset the state to `unknown`
            self._attr_is_closed = None
        else:
            self._attr_is_closed = state == CoverState.CLOSED
        self._attr_is_opening = state == CoverState.OPENING
        self._attr_is_closing = state == CoverState.CLOSING

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
                    CoverState.CLOSED
                    if self._attr_current_cover_position == DEFAULT_POSITION_CLOSED
                    else CoverState.OPEN
                )
            else:
                state = (
                    CoverState.CLOSED
                    if self.state in [CoverState.CLOSED, CoverState.CLOSING]
                    else CoverState.OPEN
                )
        elif payload == self._config[CONF_STATE_OPENING]:
            state = CoverState.OPENING
        elif payload == self._config[CONF_STATE_CLOSING]:
            state = CoverState.CLOSING
        elif payload == self._config[CONF_STATE_OPEN]:
            state = CoverState.OPEN
        elif payload == self._config[CONF_STATE_CLOSED]:
            state = CoverState.CLOSED
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
                CoverState.CLOSED
                if self.current_cover_position == 0
                else CoverState.OPEN
            )

    @callback
    @override
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

    @override
    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up.

        This method is a coroutine.
        """
        await self.async_publish_with_config(
            self._config[CONF_COMMAND_TOPIC], self._config[CONF_PAYLOAD_OPEN]
        )
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._update_state(CoverState.OPEN)
            if self._config.get(CONF_GET_POSITION_TOPIC):
                self._attr_current_cover_position = 100
            self.async_write_ha_state()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down.

        This method is a coroutine.
        """
        await self.async_publish_with_config(
            self._config[CONF_COMMAND_TOPIC], self._config[CONF_PAYLOAD_CLOSE]
        )
        if self._optimistic:
            # Optimistically assume that cover has changed state.
            self._update_state(CoverState.CLOSED)
            if self._config.get(CONF_GET_POSITION_TOPIC):
                self._attr_current_cover_position = 0
            self.async_write_ha_state()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device.

        This method is a coroutine.
        """
        await self.async_publish_with_config(
            self._config[CONF_COMMAND_TOPIC], self._config[CONF_PAYLOAD_STOP]
        )

    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover open."""
        if not self._legacy_tilt:
            await self.async_set_cover_tilt_position(
                tilt_position=self._tilt_open_percentage
            )
            return
        tilt_open_position = self._config.get(
            CONF_TILT_OPEN_POSITION, DEFAULT_TILT_OPEN_POSITION
        )
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

    def _closed_tilt_target(self) -> int:
        """Return the closed tilt position to move the slats to."""
        if len(self._tilt_closed_positions) == 1:
            return self._tilt_closed_positions[0]
        start: int | None = self._config.get(CONF_TILT_START_ANGLE)
        end: int | None = self._config.get(CONF_TILT_END_ANGLE)
        if start is not None and end is not None and abs(start) != abs(end):
            # Close at the end where the slats lie the flattest
            return 0 if abs(start) > abs(end) else 100
        if (current := self.current_cover_tilt_position) is None:
            return 0
        return 0 if current <= 50 else 100

    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover closed."""
        if not self._legacy_tilt:
            await self.async_set_cover_tilt_position(
                tilt_position=self._closed_tilt_target()
            )
            return
        tilt_closed_position = self._config.get(
            CONF_TILT_CLOSED_POSITION, DEFAULT_TILT_CLOSED_POSITION
        )
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

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        tilt_percentage = kwargs[CoverServiceArgument.TILT_POSITION]
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

    @override
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop moving the cover tilt."""
        await self.async_publish_with_config(
            self._config[CONF_TILT_COMMAND_TOPIC], self._config[CONF_PAYLOAD_STOP_TILT]
        )

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position_percentage = kwargs[CoverServiceArgument.POSITION]
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
                CoverState.CLOSED
                if position_percentage <= self._config[CONF_POSITION_CLOSED]
                else CoverState.OPEN
            )
            self._attr_current_cover_position = position_percentage
            self.async_write_ha_state()

    @override
    async def async_toggle_tilt(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if not self._legacy_tilt:
            await super().async_toggle_tilt(**kwargs)
            return
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
