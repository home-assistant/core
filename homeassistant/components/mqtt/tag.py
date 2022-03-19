"""Provides tag scanning for MQTT."""
from __future__ import annotations

import logging
from typing import TypedDict, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_PLATFORM, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from . import MqttValueTemplate, subscription
from .. import mqtt
from .const import ATTR_DISCOVERY_HASH, CONF_QOS, CONF_TOPIC
from .discovery import MQTTConfig, cancel_discovery
from .mixins import (
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    MqttDiscoveryDeviceUpdateService,
    device_info_from_config,
)
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

LOG_NAME = "Tag"

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


class MqttTagConfig(TypedDict, total=False):
    """Supply service parameters for MQTTTagScanner."""

    topic: str
    value_template: Template
    device: ConfigType


async def async_setup_tag(
    hass: HomeAssistant,
    discovery_info: MQTTConfig,
) -> None:
    """Set up the MQTT tag scanner."""
    config_entry: ConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    tag_config: MqttTagConfig
    try:
        tag_config = PLATFORM_SCHEMA(discovery_info)
    except Exception:
        cancel_discovery(hass, discovery_info)
        raise

    discovery_hash = discovery_info.discovery_data[ATTR_DISCOVERY_HASH]
    discovery_id = discovery_hash[1]

    device_id = _update_device(hass, config_entry, tag_config)
    hass.data.setdefault(TAGS, {})
    if device_id not in hass.data[TAGS]:
        hass.data[TAGS][device_id] = {}

    tag_scanner = MQTTTagScanner(
        hass,
        tag_config,
        cast(str, device_id),
        discovery_info,
        config_entry,
    )

    await tag_scanner.subscribe_topics()

    if device_id:
        hass.data[TAGS][device_id][discovery_id] = tag_scanner


def async_has_tags(hass, device_id):
    """Device has tag scanners."""
    if TAGS not in hass.data or device_id not in hass.data[TAGS]:
        return False
    return hass.data[TAGS][device_id] != {}


class MQTTTagScanner(MqttDiscoveryDeviceUpdateService):
    """MQTT Tag scanner."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: MqttTagConfig,
        device_id: str,
        discovery_info: MQTTConfig,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self._config = config
        self._config_entry = config_entry
        self.device_id = device_id
        self.discovery_data = discovery_info.discovery_data
        self.hass = hass
        self._sub_state = None
        self._value_template = None

        self._setup_from_config(config)

        MqttDiscoveryDeviceUpdateService.__init__(
            self, hass, discovery_info, device_id, config_entry, LOG_NAME
        )

    def _setup_from_config(self, config):
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE),
            hass=self.hass,
        ).async_render_with_possible_json_value

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

    async def async_tear_down(self):
        """Cleanup tag scanner."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        discovery_id = discovery_hash[1]
        self._sub_state = subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        if self.device_id:
            self.hass.data[TAGS][self.device_id].pop(discovery_id)


def _update_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None,
    config: MqttTagConfig,
) -> str | None:
    """Update device registry."""
    if config_entry is None or CONF_DEVICE not in config:
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
