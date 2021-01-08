"""MQTT component mixins and helpers."""
import json
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from . import CONF_TOPIC, DATA_MQTT, debug_info, publish
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    ATTR_DISCOVERY_TOPIC,
    CONF_QOS,
    DEFAULT_PAYLOAD_AVAILABLE,
    DEFAULT_PAYLOAD_NOT_AVAILABLE,
    DOMAIN,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
)
from .debug_info import log_messages
from .discovery import (
    MQTT_DISCOVERY_DONE,
    MQTT_DISCOVERY_UPDATED,
    clear_discovery_hash,
    set_discovery_hash,
)
from .models import Message
from .subscription import async_subscribe_topics, async_unsubscribe_topics
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_AVAILABILITY = "availability"
CONF_AVAILABILITY_TOPIC = "availability_topic"
CONF_PAYLOAD_AVAILABLE = "payload_available"
CONF_PAYLOAD_NOT_AVAILABLE = "payload_not_available"
CONF_JSON_ATTRS_TOPIC = "json_attributes_topic"
CONF_JSON_ATTRS_TEMPLATE = "json_attributes_template"

CONF_IDENTIFIERS = "identifiers"
CONF_CONNECTIONS = "connections"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_SW_VERSION = "sw_version"
CONF_VIA_DEVICE = "via_device"
CONF_DEPRECATED_VIA_HUB = "via_hub"

MQTT_AVAILABILITY_SINGLE_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_AVAILABILITY_TOPIC, "availability"): valid_subscribe_topic,
        vol.Optional(
            CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_NOT_AVAILABLE, default=DEFAULT_PAYLOAD_NOT_AVAILABLE
        ): cv.string,
    }
)

MQTT_AVAILABILITY_LIST_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_AVAILABILITY, "availability"): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Optional(CONF_TOPIC): valid_subscribe_topic,
                    vol.Optional(
                        CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
                    ): cv.string,
                    vol.Optional(
                        CONF_PAYLOAD_NOT_AVAILABLE,
                        default=DEFAULT_PAYLOAD_NOT_AVAILABLE,
                    ): cv.string,
                }
            ],
        ),
    }
)

MQTT_AVAILABILITY_SCHEMA = MQTT_AVAILABILITY_SINGLE_SCHEMA.extend(
    MQTT_AVAILABILITY_LIST_SCHEMA.schema
)


def validate_device_has_at_least_one_identifier(value: ConfigType) -> ConfigType:
    """Validate that a device info entry has at least one identifying value."""
    if value.get(CONF_IDENTIFIERS) or value.get(CONF_CONNECTIONS):
        return value
    raise vol.Invalid(
        "Device must have at least one identifying value in "
        "'identifiers' and/or 'connections'"
    )


MQTT_ENTITY_DEVICE_INFO_SCHEMA = vol.All(
    cv.deprecated(CONF_DEPRECATED_VIA_HUB, CONF_VIA_DEVICE),
    vol.Schema(
        {
            vol.Optional(CONF_IDENTIFIERS, default=list): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_CONNECTIONS, default=list): vol.All(
                cv.ensure_list, [vol.All(vol.Length(2), [cv.string])]
            ),
            vol.Optional(CONF_MANUFACTURER): cv.string,
            vol.Optional(CONF_MODEL): cv.string,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_SW_VERSION): cv.string,
            vol.Optional(CONF_VIA_DEVICE): cv.string,
        }
    ),
    validate_device_has_at_least_one_identifier,
)

MQTT_JSON_ATTRS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_JSON_ATTRS_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_JSON_ATTRS_TEMPLATE): cv.template,
    }
)


class MqttAttributes(Entity):
    """Mixin used for platforms that support JSON attributes."""

    def __init__(self, config: dict) -> None:
        """Initialize the JSON attributes mixin."""
        self._attributes = None
        self._attributes_sub_state = None
        self._attributes_config = config

    async def async_added_to_hass(self) -> None:
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        await self._attributes_subscribe_topics()

    async def attributes_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._attributes_config = config
        await self._attributes_subscribe_topics()

    async def _attributes_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        attr_tpl = self._attributes_config.get(CONF_JSON_ATTRS_TEMPLATE)
        if attr_tpl is not None:
            attr_tpl.hass = self.hass

        @callback
        @log_messages(self.hass, self.entity_id)
        def attributes_message_received(msg: Message) -> None:
            try:
                payload = msg.payload
                if attr_tpl is not None:
                    payload = attr_tpl.async_render_with_possible_json_value(payload)
                json_dict = json.loads(payload)
                if isinstance(json_dict, dict):
                    self._attributes = json_dict
                    self.async_write_ha_state()
                else:
                    _LOGGER.warning("JSON result was not a dictionary")
                    self._attributes = None
            except ValueError:
                _LOGGER.warning("Erroneous JSON: %s", payload)
                self._attributes = None

        self._attributes_sub_state = await async_subscribe_topics(
            self.hass,
            self._attributes_sub_state,
            {
                CONF_JSON_ATTRS_TOPIC: {
                    "topic": self._attributes_config.get(CONF_JSON_ATTRS_TOPIC),
                    "msg_callback": attributes_message_received,
                    "qos": self._attributes_config.get(CONF_QOS),
                }
            },
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._attributes_sub_state = await async_unsubscribe_topics(
            self.hass, self._attributes_sub_state
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes


class MqttAvailability(Entity):
    """Mixin used for platforms that report availability."""

    def __init__(self, config: dict) -> None:
        """Initialize the availability mixin."""
        self._availability_sub_state = None
        self._available = False
        self._availability_setup_from_config(config)

    async def async_added_to_hass(self) -> None:
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        await self._availability_subscribe_topics()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, MQTT_CONNECTED, self.async_mqtt_connect)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, MQTT_DISCONNECTED, self.async_mqtt_connect
            )
        )

    async def availability_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._availability_setup_from_config(config)
        await self._availability_subscribe_topics()

    def _availability_setup_from_config(self, config):
        """(Re)Setup."""
        self._avail_topics = {}
        if CONF_AVAILABILITY_TOPIC in config:
            self._avail_topics[config[CONF_AVAILABILITY_TOPIC]] = {
                CONF_PAYLOAD_AVAILABLE: config[CONF_PAYLOAD_AVAILABLE],
                CONF_PAYLOAD_NOT_AVAILABLE: config[CONF_PAYLOAD_NOT_AVAILABLE],
            }

        if CONF_AVAILABILITY in config:
            for avail in config[CONF_AVAILABILITY]:
                self._avail_topics[avail[CONF_TOPIC]] = {
                    CONF_PAYLOAD_AVAILABLE: avail[CONF_PAYLOAD_AVAILABLE],
                    CONF_PAYLOAD_NOT_AVAILABLE: avail[CONF_PAYLOAD_NOT_AVAILABLE],
                }

        self._avail_config = config

    async def _availability_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def availability_message_received(msg: Message) -> None:
            """Handle a new received MQTT availability message."""
            topic = msg.topic
            if msg.payload == self._avail_topics[topic][CONF_PAYLOAD_AVAILABLE]:
                self._available = True
            elif msg.payload == self._avail_topics[topic][CONF_PAYLOAD_NOT_AVAILABLE]:
                self._available = False

            self.async_write_ha_state()

        topics = {
            f"availability_{topic}": {
                "topic": topic,
                "msg_callback": availability_message_received,
                "qos": self._avail_config[CONF_QOS],
            }
            for topic in self._avail_topics
        }

        self._availability_sub_state = await async_subscribe_topics(
            self.hass,
            self._availability_sub_state,
            topics,
        )

    @callback
    def async_mqtt_connect(self):
        """Update state on connection/disconnection to MQTT broker."""
        if not self.hass.is_stopping:
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._availability_sub_state = await async_unsubscribe_topics(
            self.hass, self._availability_sub_state
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        if not self.hass.data[DATA_MQTT].connected and not self.hass.is_stopping:
            return False
        return not self._avail_topics or self._available


async def cleanup_device_registry(hass, device_id):
    """Remove device registry entry if there are no remaining entities or triggers."""
    # Local import to avoid circular dependencies
    # pylint: disable=import-outside-toplevel
    from . import device_trigger, tag

    device_registry = await hass.helpers.device_registry.async_get_registry()
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    if (
        device_id
        and not hass.helpers.entity_registry.async_entries_for_device(
            entity_registry, device_id, include_disabled_entities=True
        )
        and not await device_trigger.async_get_triggers(hass, device_id)
        and not tag.async_has_tags(hass, device_id)
    ):
        device_registry.async_remove_device(device_id)


class MqttDiscoveryUpdate(Entity):
    """Mixin used to handle updated discovery message."""

    def __init__(self, discovery_data, discovery_update=None) -> None:
        """Initialize the discovery update mixin."""
        self._discovery_data = discovery_data
        self._discovery_update = discovery_update
        self._remove_signal = None
        self._removed_from_hass = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to discovery updates."""
        await super().async_added_to_hass()
        self._removed_from_hass = False
        discovery_hash = (
            self._discovery_data[ATTR_DISCOVERY_HASH] if self._discovery_data else None
        )

        async def _async_remove_state_and_registry_entry(self) -> None:
            """Remove entity's state and entity registry entry.

            Remove entity from entity registry if it is registered, this also removes the state.
            If the entity is not in the entity registry, just remove the state.
            """
            entity_registry = (
                await self.hass.helpers.entity_registry.async_get_registry()
            )
            if entity_registry.async_is_registered(self.entity_id):
                entity_entry = entity_registry.async_get(self.entity_id)
                entity_registry.async_remove(self.entity_id)
                await cleanup_device_registry(self.hass, entity_entry.device_id)
            else:
                await self.async_remove()

        async def discovery_callback(payload):
            """Handle discovery update."""
            _LOGGER.info(
                "Got update for entity with hash: %s '%s'",
                discovery_hash,
                payload,
            )
            old_payload = self._discovery_data[ATTR_DISCOVERY_PAYLOAD]
            debug_info.update_entity_discovery_data(self.hass, payload, self.entity_id)
            if not payload:
                # Empty payload: Remove component
                _LOGGER.info("Removing component: %s", self.entity_id)
                self._cleanup_discovery_on_remove()
                await _async_remove_state_and_registry_entry(self)
            elif self._discovery_update:
                if old_payload != self._discovery_data[ATTR_DISCOVERY_PAYLOAD]:
                    # Non-empty, changed payload: Notify component
                    _LOGGER.info("Updating component: %s", self.entity_id)
                    await self._discovery_update(payload)
                else:
                    # Non-empty, unchanged payload: Ignore to avoid changing states
                    _LOGGER.info("Ignoring unchanged update for: %s", self.entity_id)
            async_dispatcher_send(
                self.hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )

        if discovery_hash:
            debug_info.add_entity_discovery_data(
                self.hass, self._discovery_data, self.entity_id
            )
            # Set in case the entity has been removed and is re-added, for example when changing entity_id
            set_discovery_hash(self.hass, discovery_hash)
            self._remove_signal = async_dispatcher_connect(
                self.hass,
                MQTT_DISCOVERY_UPDATED.format(discovery_hash),
                discovery_callback,
            )
            async_dispatcher_send(
                self.hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )

    async def async_removed_from_registry(self) -> None:
        """Clear retained discovery topic in broker."""
        if not self._removed_from_hass:
            discovery_topic = self._discovery_data[ATTR_DISCOVERY_TOPIC]
            publish(self.hass, discovery_topic, "", retain=True)

    @callback
    def add_to_platform_abort(self) -> None:
        """Abort adding an entity to a platform."""
        if self._discovery_data:
            discovery_hash = self._discovery_data[ATTR_DISCOVERY_HASH]
            clear_discovery_hash(self.hass, discovery_hash)
            async_dispatcher_send(
                self.hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )
        super().add_to_platform_abort()

    async def async_will_remove_from_hass(self) -> None:
        """Stop listening to signal and cleanup discovery data.."""
        self._cleanup_discovery_on_remove()

    def _cleanup_discovery_on_remove(self) -> None:
        """Stop listening to signal and cleanup discovery data."""
        if self._discovery_data and not self._removed_from_hass:
            debug_info.remove_entity_data(self.hass, self.entity_id)
            clear_discovery_hash(self.hass, self._discovery_data[ATTR_DISCOVERY_HASH])
            self._removed_from_hass = True

        if self._remove_signal:
            self._remove_signal()
            self._remove_signal = None


def device_info_from_config(config):
    """Return a device description for device registry."""
    if not config:
        return None

    info = {
        "identifiers": {(DOMAIN, id_) for id_ in config[CONF_IDENTIFIERS]},
        "connections": {tuple(x) for x in config[CONF_CONNECTIONS]},
    }

    if CONF_MANUFACTURER in config:
        info["manufacturer"] = config[CONF_MANUFACTURER]

    if CONF_MODEL in config:
        info["model"] = config[CONF_MODEL]

    if CONF_NAME in config:
        info["name"] = config[CONF_NAME]

    if CONF_SW_VERSION in config:
        info["sw_version"] = config[CONF_SW_VERSION]

    if CONF_VIA_DEVICE in config:
        info["via_device"] = (DOMAIN, config[CONF_VIA_DEVICE])

    return info


class MqttEntityDeviceInfo(Entity):
    """Mixin used for mqtt platforms that support the device registry."""

    def __init__(self, device_config: Optional[ConfigType], config_entry=None) -> None:
        """Initialize the device mixin."""
        self._device_config = device_config
        self._config_entry = config_entry

    async def device_info_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._device_config = config.get(CONF_DEVICE)
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        config_entry_id = self._config_entry.entry_id
        device_info = self.device_info

        if config_entry_id is not None and device_info is not None:
            device_info["config_entry_id"] = config_entry_id
            device_registry.async_get_or_create(**device_info)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return device_info_from_config(self._device_config)
