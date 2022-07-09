"""Support for MQTT locks."""
from __future__ import annotations

import functools
from typing import Any

import voluptuous as vol

from homeassistant.components import lock
from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
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
    async_discover_yaml_entities,
    async_setup_entry_helper,
    async_setup_platform_helper,
    warn_for_legacy_schema,
)
from .models import MqttValueTemplate

CONF_PAYLOAD_LOCK = "payload_lock"
CONF_PAYLOAD_UNLOCK = "payload_unlock"
CONF_PAYLOAD_OPEN = "payload_open"

CONF_STATE_LOCKED = "state_locked"
CONF_STATE_UNLOCKED = "state_unlocked"

DEFAULT_NAME = "MQTT Lock"
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_LOCK = "LOCK"
DEFAULT_PAYLOAD_UNLOCK = "UNLOCK"
DEFAULT_PAYLOAD_OPEN = "OPEN"
DEFAULT_STATE_LOCKED = "LOCKED"
DEFAULT_STATE_UNLOCKED = "UNLOCKED"

MQTT_LOCK_ATTRIBUTES_BLOCKED = frozenset(
    {
        lock.ATTR_CHANGED_BY,
        lock.ATTR_CODE_FORMAT,
    }
)

PLATFORM_SCHEMA_MODERN = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_LOCK, default=DEFAULT_PAYLOAD_LOCK): cv.string,
        vol.Optional(CONF_PAYLOAD_UNLOCK, default=DEFAULT_PAYLOAD_UNLOCK): cv.string,
        vol.Optional(CONF_PAYLOAD_OPEN): cv.string,
        vol.Optional(CONF_STATE_LOCKED, default=DEFAULT_STATE_LOCKED): cv.string,
        vol.Optional(CONF_STATE_UNLOCKED, default=DEFAULT_STATE_UNLOCKED): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

# Configuring MQTT Locks under the lock platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    cv.PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_MODERN.schema),
    warn_for_legacy_schema(lock.DOMAIN),
)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT locks configured under the lock platform key (deprecated)."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        lock.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT lock through configuration.yaml and dynamically through MQTT discovery."""
    # load and initialize platform config from configuration.yaml
    await async_discover_yaml_entities(hass, lock.DOMAIN)
    # setup for discovery
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, lock.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT Lock platform."""
    async_add_entities([MqttLock(hass, config, config_entry, discovery_data)])


class MqttLock(MqttEntity, LockEntity):
    """Representation of a lock that can be toggled using MQTT."""

    _entity_id_format = lock.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LOCK_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the lock."""
        self._state = False
        self._optimistic = False

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._optimistic = config[CONF_OPTIMISTIC]

        self._value_template = MqttValueTemplate(
            self._config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""
            payload = self._value_template(msg.payload)
            if payload == self._config[CONF_STATE_LOCKED]:
                self._state = True
            elif payload == self._config[CONF_STATE_UNLOCKED]:
                self._state = False

            self.async_write_ha_state()

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

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return LockEntityFeature.OPEN if CONF_PAYLOAD_OPEN in self._config else 0

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device.

        This method is a coroutine.
        """
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_LOCK],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that the lock has changed state.
            self._state = True
            self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device.

        This method is a coroutine.
        """
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_UNLOCK],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that the lock has changed state.
            self._state = False
            self.async_write_ha_state()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch.

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
            # Optimistically assume that the lock unlocks when opened.
            self._state = False
            self.async_write_ha_state()
