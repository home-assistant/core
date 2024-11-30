"""Provides tag scanning for MQTT."""

from __future__ import annotations

from collections.abc import Callable
import functools
import logging

import voluptuous as vol

from homeassistant.components import tag
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_VALUE_TEMPLATE
from homeassistant.core import HassJobType, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import ATTR_DISCOVERY_HASH, CONF_QOS, CONF_TOPIC
from .discovery import MQTTDiscoveryPayload
from .entity import (
    MqttDiscoveryDeviceUpdateMixin,
    async_handle_schema_error,
    async_setup_non_entity_entry_helper,
    send_discovery_done,
    update_device,
)
from .models import (
    DATA_MQTT,
    MqttValueTemplate,
    MqttValueTemplateException,
    ReceiveMessage,
)
from .schemas import MQTT_ENTITY_DEVICE_INFO_SCHEMA
from .subscription import EntitySubscription
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

LOG_NAME = "Tag"

TAG = "tag"

DISCOVERY_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Required(CONF_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    },
    extra=vol.REMOVE_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Set up MQTT tag scanner dynamically through MQTT discovery."""

    setup = functools.partial(_async_setup_tag, hass, config_entry=config_entry)
    async_setup_non_entity_entry_helper(hass, TAG, setup, DISCOVERY_SCHEMA)


async def _async_setup_tag(
    hass: HomeAssistant,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType,
) -> None:
    """Set up the MQTT tag scanner."""
    discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
    discovery_id = discovery_hash[1]

    device_id = update_device(hass, config_entry, config)
    if device_id is not None and device_id not in (tags := hass.data[DATA_MQTT].tags):
        tags[device_id] = {}

    tag_scanner = MQTTTagScanner(
        hass,
        config,
        device_id,
        discovery_data,
        config_entry,
    )

    await tag_scanner.subscribe_topics()

    if device_id:
        tags[device_id][discovery_id] = tag_scanner

    send_discovery_done(hass, discovery_data)


def async_has_tags(hass: HomeAssistant, device_id: str) -> bool:
    """Device has tag scanners."""
    if device_id not in (tags := hass.data[DATA_MQTT].tags):
        return False
    return tags[device_id] != {}


class MQTTTagScanner(MqttDiscoveryDeviceUpdateMixin):
    """MQTT Tag scanner."""

    _value_template: Callable[[ReceivePayloadType, str], ReceivePayloadType]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        device_id: str | None,
        discovery_data: DiscoveryInfoType,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self._config = config
        self._config_entry = config_entry
        self.device_id = device_id
        self.discovery_data = discovery_data
        self.hass = hass
        self._sub_state: dict[str, EntitySubscription] | None = None
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE)
        ).async_render_with_possible_json_value

        MqttDiscoveryDeviceUpdateMixin.__init__(
            self, hass, discovery_data, device_id, config_entry, LOG_NAME
        )

    async def async_update(self, discovery_data: MQTTDiscoveryPayload) -> None:
        """Handle MQTT tag discovery updates."""
        # Update tag scanner
        try:
            config: DiscoveryInfoType = DISCOVERY_SCHEMA(discovery_data)
        except vol.Invalid as err:
            async_handle_schema_error(discovery_data, err)
            return
        self._config = config
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE)
        ).async_render_with_possible_json_value
        update_device(self.hass, self._config_entry, config)
        await self.subscribe_topics()

    @callback
    def _async_tag_scanned(self, msg: ReceiveMessage) -> None:
        """Handle new tag scanned."""
        try:
            tag_id = str(self._value_template(msg.payload, "")).strip()
        except MqttValueTemplateException as exc:
            _LOGGER.warning(exc)
            return
        if not tag_id:  # No output from template, ignore
            return

        self.hass.async_create_task(
            tag.async_scan_tag(self.hass, tag_id, self.device_id)
        )

    async def subscribe_topics(self) -> None:
        """Subscribe to MQTT topics."""
        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_TOPIC],
                    "msg_callback": self._async_tag_scanned,
                    "qos": self._config[CONF_QOS],
                    "job_type": HassJobType.Callback,
                }
            },
        )
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    async def async_tear_down(self) -> None:
        """Cleanup tag scanner."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        discovery_id = discovery_hash[1]
        self._sub_state = subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        tags = self.hass.data[DATA_MQTT].tags
        if self.device_id in tags and discovery_id in tags[self.device_id]:
            del tags[self.device_id][discovery_id]
