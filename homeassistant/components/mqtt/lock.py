"""Support for MQTT locks."""
from __future__ import annotations

from collections.abc import Callable
import functools
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import lock
from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, TemplateVarsType

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
    warn_for_legacy_schema,
)
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import get_mqtt_data

CONF_CODE_FORMAT = "code_format"

CONF_PAYLOAD_LOCK = "payload_lock"
CONF_PAYLOAD_UNLOCK = "payload_unlock"
CONF_PAYLOAD_OPEN = "payload_open"

CONF_STATE_LOCKED = "state_locked"
CONF_STATE_LOCKING = "state_locking"
CONF_STATE_UNLOCKED = "state_unlocked"
CONF_STATE_UNLOCKING = "state_unlocking"
CONF_STATE_JAMMED = "state_jammed"

DEFAULT_NAME = "MQTT Lock"
DEFAULT_PAYLOAD_LOCK = "LOCK"
DEFAULT_PAYLOAD_UNLOCK = "UNLOCK"
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_STATE_LOCKED = "LOCKED"
DEFAULT_STATE_LOCKING = "LOCKING"
DEFAULT_STATE_UNLOCKED = "UNLOCKED"
DEFAULT_STATE_UNLOCKING = "UNLOCKING"
DEFAULT_STATE_JAMMED = "JAMMED"

MQTT_LOCK_ATTRIBUTES_BLOCKED = frozenset(
    {
        lock.ATTR_CHANGED_BY,
        lock.ATTR_CODE_FORMAT,
    }
)

PLATFORM_SCHEMA_MODERN = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_CODE_FORMAT): cv.is_regex,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_LOCK, default=DEFAULT_PAYLOAD_LOCK): cv.string,
        vol.Optional(CONF_PAYLOAD_UNLOCK, default=DEFAULT_PAYLOAD_UNLOCK): cv.string,
        vol.Optional(CONF_PAYLOAD_OPEN): cv.string,
        vol.Optional(CONF_STATE_JAMMED, default=DEFAULT_STATE_JAMMED): cv.string,
        vol.Optional(CONF_STATE_LOCKED, default=DEFAULT_STATE_LOCKED): cv.string,
        vol.Optional(CONF_STATE_LOCKING, default=DEFAULT_STATE_LOCKING): cv.string,
        vol.Optional(CONF_STATE_UNLOCKED, default=DEFAULT_STATE_UNLOCKED): cv.string,
        vol.Optional(CONF_STATE_UNLOCKING, default=DEFAULT_STATE_UNLOCKING): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

# Configuring MQTT Locks under the lock platform key was deprecated in HA Core 2022.6
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA = vol.All(
    warn_for_legacy_schema(lock.DOMAIN),
)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)

STATE_CONFIG_KEYS = [
    CONF_STATE_JAMMED,
    CONF_STATE_LOCKED,
    CONF_STATE_LOCKING,
    CONF_STATE_UNLOCKED,
    CONF_STATE_UNLOCKING,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT lock through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, lock.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT Lock platform."""
    async_add_entities([MqttLock(hass, config, config_entry, discovery_data)])


class MqttLock(MqttEntity, LockEntity):
    """Representation of a lock that can be toggled using MQTT."""

    _entity_id_format = lock.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LOCK_ATTRIBUTES_BLOCKED

    _compiled_pattern: re.Pattern[Any] | None
    _optimistic: bool
    _valid_states: list[str]
    _command_template: Callable[
        [PublishPayloadType, TemplateVarsType], PublishPayloadType
    ]
    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the lock."""
        self._attr_is_locked = False
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._optimistic = (
            config[CONF_OPTIMISTIC] or self._config.get(CONF_STATE_TOPIC) is None
        )

        self._compiled_pattern = config.get(CONF_CODE_FORMAT)
        self._attr_code_format = (
            self._compiled_pattern.pattern if self._compiled_pattern else None
        )

        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE), entity=self
        ).async_render

        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value

        self._attr_supported_features = LockEntityFeature(0)
        if CONF_PAYLOAD_OPEN in config:
            self._attr_supported_features |= LockEntityFeature.OPEN

        self._valid_states = [config[state] for state in STATE_CONFIG_KEYS]

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        topics: dict[str, dict[str, Any]] = {}
        qos: int = self._config[CONF_QOS]
        encoding: str | None = self._config[CONF_ENCODING] or None

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg: ReceiveMessage) -> None:
            """Handle new lock state messages."""
            payload = self._value_template(msg.payload)
            if payload in self._valid_states:
                self._attr_is_locked = payload == self._config[CONF_STATE_LOCKED]
                self._attr_is_locking = payload == self._config[CONF_STATE_LOCKING]
                self._attr_is_unlocking = payload == self._config[CONF_STATE_UNLOCKING]
                self._attr_is_jammed = payload == self._config[CONF_STATE_JAMMED]

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            topics[CONF_STATE_TOPIC] = {
                "topic": self._config.get(CONF_STATE_TOPIC),
                "msg_callback": message_received,
                CONF_QOS: qos,
                CONF_ENCODING: encoding,
            }

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass,
            self._sub_state,
            topics,
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device.

        This method is a coroutine.
        """
        tpl_vars: TemplateVarsType = {
            ATTR_CODE: kwargs.get(ATTR_CODE) if kwargs else None
        }
        payload = self._command_template(self._config[CONF_PAYLOAD_LOCK], tpl_vars)
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that the lock has changed state.
            self._attr_is_locked = True
            self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device.

        This method is a coroutine.
        """
        tpl_vars: TemplateVarsType = {
            ATTR_CODE: kwargs.get(ATTR_CODE) if kwargs else None
        }
        payload = self._command_template(self._config[CONF_PAYLOAD_UNLOCK], tpl_vars)
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that the lock has changed state.
            self._attr_is_locked = False
            self.async_write_ha_state()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch.

        This method is a coroutine.
        """
        tpl_vars: TemplateVarsType = {
            ATTR_CODE: kwargs.get(ATTR_CODE) if kwargs else None
        }
        payload = self._command_template(self._config[CONF_PAYLOAD_OPEN], tpl_vars)
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that the lock unlocks when opened.
            self._attr_is_locked = False
            self.async_write_ha_state()
