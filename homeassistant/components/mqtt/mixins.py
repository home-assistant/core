"""MQTT component mixins and helpers."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable
import logging
from typing import Any, Protocol, cast, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SUGGESTED_AREA,
    ATTR_SW_VERSION,
    ATTR_VIA_DEVICE,
    CONF_DEVICE,
    CONF_ENTITY_CATEGORY,
    CONF_ICON,
    CONF_MODEL,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import (
    ENTITY_CATEGORIES_SCHEMA,
    DeviceInfo,
    Entity,
    EntityCategory,
    async_generate_entity_id,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import json_loads
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import debug_info, subscription
from .client import async_publish
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    ATTR_DISCOVERY_TOPIC,
    CONF_AVAILABILITY,
    CONF_ENCODING,
    CONF_QOS,
    CONF_TOPIC,
    DATA_MQTT,
    DATA_MQTT_CONFIG,
    DATA_MQTT_RELOAD_NEEDED,
    DATA_MQTT_UPDATED_CONFIG,
    DEFAULT_ENCODING,
    DEFAULT_PAYLOAD_AVAILABLE,
    DEFAULT_PAYLOAD_NOT_AVAILABLE,
    DOMAIN,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
)
from .debug_info import log_message, log_messages
from .discovery import (
    MQTT_DISCOVERY_DONE,
    MQTT_DISCOVERY_NEW,
    MQTT_DISCOVERY_UPDATED,
    clear_discovery_hash,
    set_discovery_hash,
)
from .models import MqttValueTemplate, PublishPayloadType, ReceiveMessage
from .subscription import (
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

AVAILABILITY_ALL = "all"
AVAILABILITY_ANY = "any"
AVAILABILITY_LATEST = "latest"

AVAILABILITY_MODES = [AVAILABILITY_ALL, AVAILABILITY_ANY, AVAILABILITY_LATEST]

CONF_AVAILABILITY_MODE = "availability_mode"
CONF_AVAILABILITY_TEMPLATE = "availability_template"
CONF_AVAILABILITY_TOPIC = "availability_topic"
CONF_ENABLED_BY_DEFAULT = "enabled_by_default"
CONF_PAYLOAD_AVAILABLE = "payload_available"
CONF_PAYLOAD_NOT_AVAILABLE = "payload_not_available"
CONF_JSON_ATTRS_TOPIC = "json_attributes_topic"
CONF_JSON_ATTRS_TEMPLATE = "json_attributes_template"

CONF_IDENTIFIERS = "identifiers"
CONF_CONNECTIONS = "connections"
CONF_MANUFACTURER = "manufacturer"
CONF_SW_VERSION = "sw_version"
CONF_VIA_DEVICE = "via_device"
CONF_DEPRECATED_VIA_HUB = "via_hub"
CONF_SUGGESTED_AREA = "suggested_area"
CONF_CONFIGURATION_URL = "configuration_url"
CONF_OBJECT_ID = "object_id"

MQTT_ATTRIBUTES_BLOCKED = {
    "assumed_state",
    "available",
    "context_recent_time",
    "device_class",
    "device_info",
    "entity_category",
    "entity_picture",
    "entity_registry_enabled_default",
    "extra_state_attributes",
    "force_update",
    "icon",
    "name",
    "should_poll",
    "state",
    "supported_features",
    "unique_id",
    "unit_of_measurement",
}

MQTT_AVAILABILITY_SINGLE_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_AVAILABILITY_TOPIC, "availability"): valid_subscribe_topic,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
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
        vol.Optional(CONF_AVAILABILITY_MODE, default=AVAILABILITY_LATEST): vol.All(
            cv.string, vol.In(AVAILABILITY_MODES)
        ),
        vol.Exclusive(CONF_AVAILABILITY, "availability"): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_TOPIC): valid_subscribe_topic,
                    vol.Optional(
                        CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
                    ): cv.string,
                    vol.Optional(
                        CONF_PAYLOAD_NOT_AVAILABLE,
                        default=DEFAULT_PAYLOAD_NOT_AVAILABLE,
                    ): cv.string,
                    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
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
            vol.Optional(CONF_SUGGESTED_AREA): cv.string,
            vol.Optional(CONF_CONFIGURATION_URL): cv.url,
        }
    ),
    validate_device_has_at_least_one_identifier,
)

MQTT_ENTITY_COMMON_SCHEMA = MQTT_AVAILABILITY_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Optional(CONF_ENABLED_BY_DEFAULT, default=True): cv.boolean,
        vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_JSON_ATTRS_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_JSON_ATTRS_TEMPLATE): cv.template,
        vol.Optional(CONF_OBJECT_ID): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


def warn_for_legacy_schema(domain: str) -> Callable:
    """Warn once when a legacy platform schema is used."""
    warned = set()

    def validator(config: ConfigType) -> ConfigType:
        """Return a validator."""
        nonlocal warned

        if domain in warned:
            return config

        _LOGGER.warning(
            "Manually configured MQTT %s(s) found under platform key '%s', "
            "please move to the mqtt integration key, see "
            "https://www.home-assistant.io/integrations/%s.mqtt/#new_format",
            domain,
            domain,
            domain,
        )
        warned.add(domain)
        return config

    return validator


class SetupEntity(Protocol):
    """Protocol type for async_setup_entities."""

    async def __call__(
        self,
        hass: HomeAssistant,
        async_add_entities: AddEntitiesCallback,
        config: ConfigType,
        config_entry: ConfigEntry | None = None,
        discovery_data: dict[str, Any] | None = None,
    ) -> None:
        """Define setup_entities type."""


async def async_discover_yaml_entities(
    hass: HomeAssistant, platform_domain: str
) -> None:
    """Discover entities for a platform."""
    if DATA_MQTT_UPDATED_CONFIG in hass.data:
        # The platform has been reloaded
        config_yaml = hass.data[DATA_MQTT_UPDATED_CONFIG]
    else:
        config_yaml = hass.data.get(DATA_MQTT_CONFIG, {})
    if not config_yaml:
        return
    if platform_domain not in config_yaml:
        return
    await asyncio.gather(
        *(
            discovery.async_load_platform(hass, platform_domain, DOMAIN, config, {})
            for config in await async_get_platform_config_from_yaml(
                hass, platform_domain, config_yaml
            )
        )
    )


async def async_get_platform_config_from_yaml(
    hass: HomeAssistant,
    platform_domain: str,
    config_yaml: ConfigType = None,
) -> list[ConfigType]:
    """Return a list of validated configurations for the domain."""

    if config_yaml is None:
        config_yaml = hass.data.get(DATA_MQTT_CONFIG)
    if not config_yaml:
        return []
    if not (platform_configs := config_yaml.get(platform_domain)):
        return []
    return platform_configs


async def async_setup_entry_helper(hass, domain, async_setup, schema):
    """Set up entity, automation or tag creation dynamically through MQTT discovery."""

    async def async_discover(discovery_payload):
        """Discover and add an MQTT entity, automation or tag."""
        discovery_data = discovery_payload.discovery_data
        try:
            config = schema(discovery_payload)
            await async_setup(config, discovery_data=discovery_data)
        except Exception:
            discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
            clear_discovery_hash(hass, discovery_hash)
            async_dispatcher_send(
                hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
            )
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(domain, "mqtt"), async_discover
    )


async def async_setup_platform_helper(
    hass: HomeAssistant,
    platform_domain: str,
    config: ConfigType | DiscoveryInfoType,
    async_add_entities: AddEntitiesCallback,
    async_setup_entities: SetupEntity,
) -> None:
    """Return true if platform setup should be aborted."""
    if not bool(hass.config_entries.async_entries(DOMAIN)):
        hass.data[DATA_MQTT_RELOAD_NEEDED] = None
        _LOGGER.warning(
            "MQTT integration is not setup, skipping setup of manually configured "
            "MQTT %s",
            platform_domain,
        )
        return
    await async_setup_entities(hass, async_add_entities, config)


def init_entity_id_from_config(hass, entity, config, entity_id_format):
    """Set entity_id from object_id if defined in config."""
    if CONF_OBJECT_ID in config:
        entity.entity_id = async_generate_entity_id(
            entity_id_format, config[CONF_OBJECT_ID], None, hass
        )


class MqttAttributes(Entity):
    """Mixin used for platforms that support JSON attributes."""

    _attributes_extra_blocked: frozenset[str] = frozenset()

    def __init__(self, config: dict) -> None:
        """Initialize the JSON attributes mixin."""
        self._attributes: dict | None = None
        self._attributes_sub_state = None
        self._attributes_config = config

    async def async_added_to_hass(self) -> None:
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        self._attributes_prepare_subscribe_topics()
        await self._attributes_subscribe_topics()

    def attributes_prepare_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._attributes_config = config
        self._attributes_prepare_subscribe_topics()

    async def attributes_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        await self._attributes_subscribe_topics()

    def _attributes_prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        attr_tpl = MqttValueTemplate(
            self._attributes_config.get(CONF_JSON_ATTRS_TEMPLATE), entity=self
        ).async_render_with_possible_json_value

        @callback
        @log_messages(self.hass, self.entity_id)
        def attributes_message_received(msg: ReceiveMessage) -> None:
            try:
                payload = attr_tpl(msg.payload)
                json_dict = json_loads(payload) if isinstance(payload, str) else None
                if isinstance(json_dict, dict):
                    filtered_dict = {
                        k: v
                        for k, v in json_dict.items()
                        if k not in MQTT_ATTRIBUTES_BLOCKED
                        and k not in self._attributes_extra_blocked
                    }
                    self._attributes = filtered_dict
                    self.async_write_ha_state()
                else:
                    _LOGGER.warning("JSON result was not a dictionary")
                    self._attributes = None
            except ValueError:
                _LOGGER.warning("Erroneous JSON: %s", payload)
                self._attributes = None

        self._attributes_sub_state = async_prepare_subscribe_topics(
            self.hass,
            self._attributes_sub_state,
            {
                CONF_JSON_ATTRS_TOPIC: {
                    "topic": self._attributes_config.get(CONF_JSON_ATTRS_TOPIC),
                    "msg_callback": attributes_message_received,
                    "qos": self._attributes_config.get(CONF_QOS),
                    "encoding": self._attributes_config[CONF_ENCODING] or None,
                }
            },
        )

    async def _attributes_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await async_subscribe_topics(self.hass, self._attributes_sub_state)

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._attributes_sub_state = async_unsubscribe_topics(
            self.hass, self._attributes_sub_state
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes


class MqttAvailability(Entity):
    """Mixin used for platforms that report availability."""

    def __init__(self, config: dict) -> None:
        """Initialize the availability mixin."""
        self._availability_sub_state = None
        self._available: dict = {}
        self._available_latest = False
        self._availability_setup_from_config(config)

    async def async_added_to_hass(self) -> None:
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        self._availability_prepare_subscribe_topics()
        await self._availability_subscribe_topics()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, MQTT_CONNECTED, self.async_mqtt_connect)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, MQTT_DISCONNECTED, self.async_mqtt_connect
            )
        )

    def availability_prepare_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._availability_setup_from_config(config)
        self._availability_prepare_subscribe_topics()

    async def availability_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        await self._availability_subscribe_topics()

    def _availability_setup_from_config(self, config):
        """(Re)Setup."""
        self._avail_topics = {}
        if CONF_AVAILABILITY_TOPIC in config:
            self._avail_topics[config[CONF_AVAILABILITY_TOPIC]] = {
                CONF_PAYLOAD_AVAILABLE: config[CONF_PAYLOAD_AVAILABLE],
                CONF_PAYLOAD_NOT_AVAILABLE: config[CONF_PAYLOAD_NOT_AVAILABLE],
                CONF_AVAILABILITY_TEMPLATE: config.get(CONF_AVAILABILITY_TEMPLATE),
            }

        if CONF_AVAILABILITY in config:
            for avail in config[CONF_AVAILABILITY]:
                self._avail_topics[avail[CONF_TOPIC]] = {
                    CONF_PAYLOAD_AVAILABLE: avail[CONF_PAYLOAD_AVAILABLE],
                    CONF_PAYLOAD_NOT_AVAILABLE: avail[CONF_PAYLOAD_NOT_AVAILABLE],
                    CONF_AVAILABILITY_TEMPLATE: avail.get(CONF_VALUE_TEMPLATE),
                }

        for avail_topic_conf in self._avail_topics.values():
            avail_topic_conf[CONF_AVAILABILITY_TEMPLATE] = MqttValueTemplate(
                avail_topic_conf[CONF_AVAILABILITY_TEMPLATE],
                entity=self,
            ).async_render_with_possible_json_value

        self._avail_config = config

    def _availability_prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def availability_message_received(msg: ReceiveMessage) -> None:
            """Handle a new received MQTT availability message."""
            topic = msg.topic
            payload = self._avail_topics[topic][CONF_AVAILABILITY_TEMPLATE](msg.payload)
            if payload == self._avail_topics[topic][CONF_PAYLOAD_AVAILABLE]:
                self._available[topic] = True
                self._available_latest = True
            elif payload == self._avail_topics[topic][CONF_PAYLOAD_NOT_AVAILABLE]:
                self._available[topic] = False
                self._available_latest = False

            self.async_write_ha_state()

        self._available = {
            topic: (self._available[topic] if topic in self._available else False)
            for topic in self._avail_topics
        }
        topics = {
            f"availability_{topic}": {
                "topic": topic,
                "msg_callback": availability_message_received,
                "qos": self._avail_config[CONF_QOS],
                "encoding": self._avail_config[CONF_ENCODING] or None,
            }
            for topic in self._avail_topics
        }

        self._availability_sub_state = async_prepare_subscribe_topics(
            self.hass,
            self._availability_sub_state,
            topics,
        )

    async def _availability_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await async_subscribe_topics(self.hass, self._availability_sub_state)

    @callback
    def async_mqtt_connect(self):
        """Update state on connection/disconnection to MQTT broker."""
        if not self.hass.is_stopping:
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._availability_sub_state = async_unsubscribe_topics(
            self.hass, self._availability_sub_state
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        if not self.hass.data[DATA_MQTT].connected and not self.hass.is_stopping:
            return False
        if not self._avail_topics:
            return True
        if self._avail_config[CONF_AVAILABILITY_MODE] == AVAILABILITY_ALL:
            return all(self._available.values())
        if self._avail_config[CONF_AVAILABILITY_MODE] == AVAILABILITY_ANY:
            return any(self._available.values())
        return self._available_latest


async def cleanup_device_registry(
    hass: HomeAssistant, device_id: str | None, config_entry_id: str | None
) -> None:
    """Remove MQTT from the device registry entry if there are no remaining entities, triggers or tags."""
    # Local import to avoid circular dependencies
    # pylint: disable-next=import-outside-toplevel
    from . import device_trigger, tag

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    if (
        device_id
        and config_entry_id
        and not er.async_entries_for_device(
            entity_registry, device_id, include_disabled_entities=False
        )
        and not await device_trigger.async_get_triggers(hass, device_id)
        and not tag.async_has_tags(hass, device_id)
    ):
        device_registry.async_update_device(
            device_id, remove_config_entry_id=config_entry_id
        )


def get_discovery_hash(discovery_data: dict) -> tuple:
    """Get the discovery hash from the discovery data."""
    return discovery_data[ATTR_DISCOVERY_HASH]


def send_discovery_done(hass: HomeAssistant, discovery_data: dict) -> None:
    """Acknowledge a discovery message has been handled."""
    discovery_hash = get_discovery_hash(discovery_data)
    async_dispatcher_send(hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None)


def stop_discovery_updates(
    hass: HomeAssistant,
    discovery_data: dict,
    remove_discovery_updated: Callable[[], None] | None = None,
) -> None:
    """Stop discovery updates of being sent."""
    if remove_discovery_updated:
        remove_discovery_updated()
        remove_discovery_updated = None
    discovery_hash = get_discovery_hash(discovery_data)
    clear_discovery_hash(hass, discovery_hash)


async def async_remove_discovery_payload(hass: HomeAssistant, discovery_data: dict):
    """Clear retained discovery topic in broker to avoid rediscovery after a restart of HA."""
    discovery_topic = discovery_data[ATTR_DISCOVERY_TOPIC]
    await async_publish(hass, discovery_topic, "", retain=True)


class MqttDiscoveryDeviceUpdate:
    """Add support for auto discovery for platforms without an entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        discovery_data: dict,
        device_id: str | None,
        config_entry: ConfigEntry,
        log_name: str,
    ) -> None:
        """Initialize the update service."""

        self.hass = hass
        self.log_name = log_name

        self._discovery_data = discovery_data
        self._device_id = device_id
        self._config_entry = config_entry
        self._config_entry_id = config_entry.entry_id
        self._skip_device_removal: bool = False

        discovery_hash = get_discovery_hash(discovery_data)
        self._remove_discovery_updated = async_dispatcher_connect(
            hass,
            MQTT_DISCOVERY_UPDATED.format(discovery_hash),
            self.async_discovery_update,
        )
        if device_id is not None:
            self._remove_device_updated = hass.bus.async_listen(
                EVENT_DEVICE_REGISTRY_UPDATED, self._async_device_removed
            )
        _LOGGER.info(
            "%s %s has been initialized",
            self.log_name,
            discovery_hash,
        )

    async def async_discovery_update(
        self,
        discovery_payload: DiscoveryInfoType | None,
    ) -> None:
        """Handle discovery update."""
        discovery_hash = get_discovery_hash(self._discovery_data)
        _LOGGER.info(
            "Got update for %s with hash: %s '%s'",
            self.log_name,
            discovery_hash,
            discovery_payload,
        )
        if (
            discovery_payload
            and discovery_payload != self._discovery_data[ATTR_DISCOVERY_PAYLOAD]
        ):
            _LOGGER.info(
                "%s %s updating",
                self.log_name,
                discovery_hash,
            )
            await self.async_update(discovery_payload)
        if not discovery_payload:
            # Unregister and clean up the current discovery instance
            stop_discovery_updates(
                self.hass, self._discovery_data, self._remove_discovery_updated
            )
            await self._async_tear_down()
            send_discovery_done(self.hass, self._discovery_data)
            _LOGGER.info(
                "%s %s has been removed",
                self.log_name,
                discovery_hash,
            )
        else:
            # Normal update without change
            send_discovery_done(self.hass, self._discovery_data)
            _LOGGER.info(
                "%s %s no changes",
                self.log_name,
                discovery_hash,
            )
            return

    async def _async_device_removed(self, event: Event) -> None:
        """Handle the manual removal of a device."""
        if self._skip_device_removal or not async_removed_from_device(
            self.hass, event, cast(str, self._device_id), self._config_entry_id
        ):
            return
        # Prevent a second cleanup round after the device is removed
        self._remove_device_updated()
        self._skip_device_removal = True
        # Unregister and clean up and publish an empty payload
        # so the service is not rediscovered after a restart
        stop_discovery_updates(
            self.hass, self._discovery_data, self._remove_discovery_updated
        )
        await self._async_tear_down()
        await async_remove_discovery_payload(self.hass, self._discovery_data)

    async def _async_tear_down(self) -> None:
        """Handle the cleanup of the discovery service."""
        # Cleanup platform resources
        await self.async_tear_down()
        # remove the service for auto discovery updates and clean up the device registry
        if not self._skip_device_removal:
            # Prevent a second cleanup round after the device is removed
            self._skip_device_removal = True
            await cleanup_device_registry(
                self.hass, self._device_id, self._config_entry_id
            )

    async def async_update(self, discovery_data: dict) -> None:
        """Handle the update of platform specific parts, extend to the platform."""

    @abstractmethod
    async def async_tear_down(self) -> None:
        """Handle the cleanup of platform specific parts, extend to the platform."""


class MqttDiscoveryUpdate(Entity):
    """Mixin used to handle updated discovery message for entity based platforms."""

    def __init__(self, discovery_data, discovery_update=None) -> None:
        """Initialize the discovery update mixin."""
        self._discovery_data = discovery_data
        self._discovery_update = discovery_update
        self._remove_discovery_updated: Callable | None = None
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
            entity_registry = er.async_get(self.hass)
            if entity_entry := entity_registry.async_get(self.entity_id):
                entity_registry.async_remove(self.entity_id)
                await cleanup_device_registry(
                    self.hass, entity_entry.device_id, entity_entry.config_entry_id
                )
            else:
                await self.async_remove(force_remove=True)

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
            send_discovery_done(self.hass, self._discovery_data)

        if discovery_hash:
            debug_info.add_entity_discovery_data(
                self.hass, self._discovery_data, self.entity_id
            )
            # Set in case the entity has been removed and is re-added, for example when changing entity_id
            set_discovery_hash(self.hass, discovery_hash)
            self._remove_discovery_updated = async_dispatcher_connect(
                self.hass,
                MQTT_DISCOVERY_UPDATED.format(discovery_hash),
                discovery_callback,
            )

    async def async_removed_from_registry(self) -> None:
        """Clear retained discovery topic in broker."""
        if not self._removed_from_hass:
            # Stop subscribing to discovery updates to not trigger when we clear the
            # discovery topic
            self._cleanup_discovery_on_remove()

            # Clear the discovery topic so the entity is not rediscovered after a restart
            await async_remove_discovery_payload(self.hass, self._discovery_data)

    @callback
    def add_to_platform_abort(self) -> None:
        """Abort adding an entity to a platform."""
        if self._discovery_data:
            stop_discovery_updates(self.hass, self._discovery_data)
            send_discovery_done(self.hass, self._discovery_data)
        super().add_to_platform_abort()

    async def async_will_remove_from_hass(self) -> None:
        """Stop listening to signal and cleanup discovery data.."""
        self._cleanup_discovery_on_remove()

    def _cleanup_discovery_on_remove(self) -> None:
        """Stop listening to signal and cleanup discovery data."""
        if self._discovery_data and not self._removed_from_hass:
            stop_discovery_updates(
                self.hass, self._discovery_data, self._remove_discovery_updated
            )
            self._removed_from_hass = True


def device_info_from_config(config) -> DeviceInfo | None:
    """Return a device description for device registry."""
    if not config:
        return None

    info = DeviceInfo(
        identifiers={(DOMAIN, id_) for id_ in config[CONF_IDENTIFIERS]},
        connections={(conn_[0], conn_[1]) for conn_ in config[CONF_CONNECTIONS]},
    )

    if CONF_MANUFACTURER in config:
        info[ATTR_MANUFACTURER] = config[CONF_MANUFACTURER]

    if CONF_MODEL in config:
        info[ATTR_MODEL] = config[CONF_MODEL]

    if CONF_NAME in config:
        info[ATTR_NAME] = config[CONF_NAME]

    if CONF_SW_VERSION in config:
        info[ATTR_SW_VERSION] = config[CONF_SW_VERSION]

    if CONF_VIA_DEVICE in config:
        info[ATTR_VIA_DEVICE] = (DOMAIN, config[CONF_VIA_DEVICE])

    if CONF_SUGGESTED_AREA in config:
        info[ATTR_SUGGESTED_AREA] = config[CONF_SUGGESTED_AREA]

    if CONF_CONFIGURATION_URL in config:
        info[ATTR_CONFIGURATION_URL] = config[CONF_CONFIGURATION_URL]

    return info


class MqttEntityDeviceInfo(Entity):
    """Mixin used for mqtt platforms that support the device registry."""

    def __init__(self, device_config: ConfigType | None, config_entry=None) -> None:
        """Initialize the device mixin."""
        self._device_config = device_config
        self._config_entry = config_entry

    def device_info_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._device_config = config.get(CONF_DEVICE)
        device_registry = dr.async_get(self.hass)
        config_entry_id = self._config_entry.entry_id
        device_info = self.device_info

        if config_entry_id is not None and device_info is not None:
            device_registry.async_get_or_create(
                config_entry_id=config_entry_id, **device_info
            )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""
        return device_info_from_config(self._device_config)


class MqttEntity(
    MqttAttributes,
    MqttAvailability,
    MqttDiscoveryUpdate,
    MqttEntityDeviceInfo,
):
    """Representation of an MQTT entity."""

    _entity_id_format: str

    def __init__(self, hass, config, config_entry, discovery_data):
        """Init the MQTT Entity."""
        self.hass = hass
        self._config = config
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._sub_state = None

        # Load config
        self._setup_from_config(self._config)

        # Initialize entity_id from config
        self._init_entity_id()

        # Initialize mixin classes
        MqttAttributes.__init__(self, config)
        MqttAvailability.__init__(self, config)
        MqttDiscoveryUpdate.__init__(self, discovery_data, self.discovery_update)
        MqttEntityDeviceInfo.__init__(self, config.get(CONF_DEVICE), config_entry)

    def _init_entity_id(self):
        """Set entity_id from object_id if defined in config."""
        init_entity_id_from_config(
            self.hass, self, self._config, self._entity_id_format
        )

    @final
    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        self._prepare_subscribe_topics()
        await self._subscribe_topics()
        await self.mqtt_async_added_to_hass()
        if self._discovery_data is not None:
            send_discovery_done(self.hass, self._discovery_data)

    async def mqtt_async_added_to_hass(self):
        """Call before the discovery message is acknowledged.

        To be extended by subclasses.
        """

    async def discovery_update(self, discovery_payload):
        """Handle updated discovery message."""
        config = self.config_schema()(discovery_payload)
        self._config = config
        self._setup_from_config(self._config)

        # Prepare MQTT subscriptions
        self.attributes_prepare_discovery_update(config)
        self.availability_prepare_discovery_update(config)
        self.device_info_discovery_update(config)
        self._prepare_subscribe_topics()

        # Finalize MQTT subscriptions
        await self.attributes_discovery_update(config)
        await self.availability_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        await MqttAttributes.async_will_remove_from_hass(self)
        await MqttAvailability.async_will_remove_from_hass(self)
        await MqttDiscoveryUpdate.async_will_remove_from_hass(self)
        debug_info.remove_entity_data(self.hass, self.entity_id)

    async def async_publish(
        self,
        topic: str,
        payload: PublishPayloadType,
        qos: int = 0,
        retain: bool = False,
        encoding: str = DEFAULT_ENCODING,
    ):
        """Publish message to an MQTT topic."""
        log_message(self.hass, self.entity_id, topic, payload, qos, retain)
        await async_publish(
            self.hass,
            topic,
            payload,
            qos,
            retain,
            encoding,
        )

    @staticmethod
    @abstractmethod
    def config_schema():
        """Return the config schema."""

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""

    @abstractmethod
    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""

    @abstractmethod
    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._config[CONF_ENABLED_BY_DEFAULT]

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category if any."""
        return self._config.get(CONF_ENTITY_CATEGORY)

    @property
    def icon(self):
        """Return icon of the entity if any."""
        return self._config.get(CONF_ICON)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._config.get(CONF_NAME)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id


def update_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    config: ConfigType,
) -> str | None:
    """Update device registry."""
    if CONF_DEVICE not in config:
        return None

    device = None
    device_registry = dr.async_get(hass)
    config_entry_id = config_entry.entry_id
    device_info = device_info_from_config(config[CONF_DEVICE])

    if config_entry_id is not None and device_info is not None:
        update_device_info = cast(dict, device_info)
        update_device_info["config_entry_id"] = config_entry_id
        device = device_registry.async_get_or_create(**update_device_info)

    return device.id if device else None


@callback
def async_removed_from_device(
    hass: HomeAssistant, event: Event, mqtt_device_id: str, config_entry_id: str
) -> bool:
    """Check if the passed event indicates MQTT was removed from a device."""
    device_id = event.data["device_id"]
    if event.data["action"] not in ("remove", "update"):
        return False

    if device_id != mqtt_device_id:
        return False

    if event.data["action"] == "update":
        if "config_entries" not in event.data["changes"]:
            return False
        device_registry = dr.async_get(hass)
        if not (device_entry := device_registry.async_get(device_id)):
            # The device is already removed, do cleanup when we get "remove" event
            return False
        if config_entry_id in device_entry.config_entries:
            # Not removed from device
            return False

    return True
