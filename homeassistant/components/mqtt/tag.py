"""Provides tag scanning for MQTT."""
import functools
import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICE, CONF_PLATFORM, CONF_VALUE_TEMPLATE
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from . import MqttValueTemplate, subscription
from .. import mqtt
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_TOPIC,
    CONF_QOS,
    CONF_TOPIC,
    DOMAIN,
)
from .discovery import MQTT_DISCOVERY_DONE, MQTT_DISCOVERY_UPDATED, clear_discovery_hash
from .mixins import (
    CONF_CONNECTIONS,
    CONF_IDENTIFIERS,
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    async_removed_from_device,
    async_setup_entry_helper,
    cleanup_device_registry,
    device_info_from_config,
)
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

TAG = "tag"
TAGS = "mqtt_tags"

PLATFORM_SCHEMA = mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Optional(CONF_PLATFORM): "mqtt",
        vol.Required(CONF_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    },
    extra=vol.REMOVE_EXTRA,
)


async def async_setup_entry(hass, config_entry):
    """Set up MQTT tag scan dynamically through MQTT discovery."""
    setup = functools.partial(async_setup_tag, hass, config_entry=config_entry)
    await async_setup_entry_helper(hass, "tag", setup, PLATFORM_SCHEMA)


async def async_setup_tag(hass, config, config_entry, discovery_data):
    """Set up the MQTT tag scanner."""
    discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
    discovery_id = discovery_hash[1]

    device_id = None
    if CONF_DEVICE in config:
        _update_device(hass, config_entry, config)

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(
            {(DOMAIN, id_) for id_ in config[CONF_DEVICE][CONF_IDENTIFIERS]},
            {tuple(x) for x in config[CONF_DEVICE][CONF_CONNECTIONS]},
        )

        if device is None:
            return
        device_id = device.id

        if TAGS not in hass.data:
            hass.data[TAGS] = {}
        if device_id not in hass.data[TAGS]:
            hass.data[TAGS][device_id] = {}

    tag_scanner = MQTTTagScanner(
        hass,
        config,
        device_id,
        discovery_data,
        config_entry,
    )

    await tag_scanner.setup()

    if device_id:
        hass.data[TAGS][device_id][discovery_id] = tag_scanner


def async_has_tags(hass, device_id):
    """Device has tag scanners."""
    if TAGS not in hass.data or device_id not in hass.data[TAGS]:
        return False
    return hass.data[TAGS][device_id] != {}


class MQTTTagScanner:
    """MQTT Tag scanner."""

    def __init__(self, hass, config, device_id, discovery_data, config_entry):
        """Initialize."""
        self._config = config
        self._config_entry = config_entry
        self.device_id = device_id
        self.discovery_data = discovery_data
        self.hass = hass
        self._remove_discovery = None
        self._remove_device_updated = None
        self._sub_state = None
        self._value_template = None

        self._setup_from_config(config)

    async def discovery_update(self, payload):
        """Handle discovery update."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        _LOGGER.info(
            "Got update for tag scanner with hash: %s '%s'", discovery_hash, payload
        )
        if not payload:
            # Empty payload: Remove tag scanner
            _LOGGER.info("Removing tag scanner: %s", discovery_hash)
            self.tear_down()
            if self.device_id:
                await cleanup_device_registry(
                    self.hass, self.device_id, self._config_entry.entry_id
                )
        else:
            # Non-empty payload: Update tag scanner
            _LOGGER.info("Updating tag scanner: %s", discovery_hash)
            config = PLATFORM_SCHEMA(payload)
            self._config = config
            if self.device_id:
                _update_device(self.hass, self._config_entry, config)
            self._setup_from_config(config)
            await self.subscribe_topics()

        async_dispatcher_send(
            self.hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
        )

    def _setup_from_config(self, config):
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE),
            hass=self.hass,
        ).async_render_with_possible_json_value

    async def setup(self):
        """Set up the MQTT tag scanner."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        await self.subscribe_topics()
        if self.device_id:
            self._remove_device_updated = self.hass.bus.async_listen(
                EVENT_DEVICE_REGISTRY_UPDATED, self.device_updated
            )
        self._remove_discovery = async_dispatcher_connect(
            self.hass,
            MQTT_DISCOVERY_UPDATED.format(discovery_hash),
            self.discovery_update,
        )
        async_dispatcher_send(
            self.hass, MQTT_DISCOVERY_DONE.format(discovery_hash), None
        )

    async def subscribe_topics(self):
        """Subscribe to MQTT topics."""

        async def tag_scanned(msg):
            tag_id = self._value_template(msg.payload, "").strip()
            if not tag_id:  # No output from template, ignore
                return

            # Importing tag via hass.components in case it is overridden
            # in a custom_components (custom_components.tag)
            tag = self.hass.components.tag
            await tag.async_scan_tag(tag_id, self.device_id)

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_TOPIC],
                    "msg_callback": tag_scanned,
                    "qos": self._config[CONF_QOS],
                }
            },
        )
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def device_updated(self, event):
        """Handle the update or removal of a device."""
        if not async_removed_from_device(
            self.hass, event, self.device_id, self._config_entry.entry_id
        ):
            return

        # Stop subscribing to discovery updates to not trigger when we clear the
        # discovery topic
        self.tear_down()

        # Clear the discovery topic so the entity is not rediscovered after a restart
        discovery_topic = self.discovery_data[ATTR_DISCOVERY_TOPIC]
        mqtt.publish(self.hass, discovery_topic, "", retain=True)

    def tear_down(self):
        """Cleanup tag scanner."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        discovery_id = discovery_hash[1]

        clear_discovery_hash(self.hass, discovery_hash)
        if self.device_id:
            self._remove_device_updated()
        self._remove_discovery()

        self._sub_state = subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        if self.device_id:
            self.hass.data[TAGS][self.device_id].pop(discovery_id)


def _update_device(hass, config_entry, config):
    """Update device registry."""
    device_registry = dr.async_get(hass)
    config_entry_id = config_entry.entry_id
    device_info = device_info_from_config(config[CONF_DEVICE])

    if config_entry_id is not None and device_info is not None:
        device_info["config_entry_id"] = config_entry_id
        device_registry.async_get_or_create(**device_info)
