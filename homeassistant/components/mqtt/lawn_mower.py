"""Support for MQTT lawn mowers."""
from __future__ import annotations

from collections.abc import Callable
import contextlib
import functools
import logging

import voluptuous as vol

from homeassistant.components import lawn_mower
from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_SUPPORTED_FEATURES,
    DEFAULT_OPTIMISTIC,
    DEFAULT_RETAIN,
)
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import get_mqtt_data, valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_OPTIONS = "options"

DEFAULT_NAME = "MQTT Lawn Mower"
ENTITY_ID_FORMAT = lawn_mower.DOMAIN + ".{}"

MQTT_LAWN_MOWER_ATTRIBUTES_BLOCKED: frozenset[str] = frozenset()

_SUPPORTED_FEATURES = {
    "dock": LawnMowerEntityFeature.DOCK,
    "pause": LawnMowerEntityFeature.PAUSE,
    "start_mowing": LawnMowerEntityFeature.START_MOWING,
}

PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_SUPPORTED_FEATURES, default=list(_SUPPORTED_FEATURES)): [
            vol.In(_SUPPORTED_FEATURES)
        ],
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = vol.All(PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT lawn mower through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, lawn_mower.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT lawn mower."""
    async_add_entities([MqttLawnMower(hass, config, config_entry, discovery_data)])


class MqttLawnMower(MqttEntity, LawnMowerEntity, RestoreEntity):
    """Representation of an MQTT lawn mower."""

    _default_name = DEFAULT_NAME
    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LAWN_MOWER_ATTRIBUTES_BLOCKED
    _command_template: Callable[[PublishPayloadType], PublishPayloadType]
    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]
    _optimistic: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the MQTT lawn mower."""
        self._attr_current_option = None
        LawnMowerEntity.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._optimistic = config[CONF_OPTIMISTIC]

        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value
        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE), entity=self
        ).async_render

        for feature in self._config[CONF_SUPPORTED_FEATURES]:
            self._attr_supported_features |= _SUPPORTED_FEATURES[feature]

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            payload = str(self._value_template(msg.payload))
            if not payload:
                _LOGGER.debug(
                    "Invalid empty activity payload from topic %s, for entity %s",
                    msg.topic,
                    self.entity_id,
                )
                return
            if payload.lower() == "none":
                self._attr_activity = None
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)
                return

            try:
                self._attr_activity = LawnMowerActivity(payload)
            except ValueError:
                _LOGGER.error(
                    "Invalid activity for %s: '%s' (valid activies: %s)",
                    self.entity_id,
                    payload,
                    [option.value for option in LawnMowerActivity],
                )
                return
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            self._sub_state = subscription.async_prepare_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._config.get(CONF_STATE_TOPIC),
                        "msg_callback": message_received,
                        "qos": self._config[CONF_QOS],
                        "encoding": self._config[CONF_ENCODING] or None,
                    }
                },
            )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

        if self._optimistic and (last_state := await self.async_get_last_state()):
            with contextlib.suppress(ValueError):
                self._attr_activity = LawnMowerActivity(last_state.state)

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    async def _async_operate(self, option: str, activity: LawnMowerActivity) -> None:
        """Execute operation."""
        payload = self._command_template(option)
        if self._optimistic:
            self._attr_activity = activity
            self.async_write_ha_state()

        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    async def async_start_mowing(self) -> None:
        """Start or resume mowing."""
        await self._async_operate("start_mowing", LawnMowerActivity.MOWING)

    async def async_dock(self) -> None:
        """Dock the mower."""
        await self._async_operate("dock", LawnMowerActivity.DOCKED)

    async def async_pause(self) -> None:
        """Pause the lawn mower."""
        await self._async_operate("pause", LawnMowerActivity.PAUSED)
