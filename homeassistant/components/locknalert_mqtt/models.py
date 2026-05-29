"""Data models shared across LocknAlert MQTT modules."""

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any, TypedDict

from aiolocknalert.models import ReceiveMessage

from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, VolSchemaType
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from aiolocknalert.client import Subscription
    from paho.mqtt.client import MQTTMessage

    from .client import MQTT
    from .discovery import MQTTDiscoveryPayload

_LOGGER = logging.getLogger(__name__)

type PublishPayloadType = str | bytes | int | float | None
type MessageCallbackType = Callable[[ReceiveMessage], None]


class PayloadSentinel(StrEnum):
    """Sentinel for `async_render_with_possible_json_value`."""

    NONE = "none"
    DEFAULT = "default"


class PendingDiscovered(TypedDict):
    """Pending discovered items."""

    pending: deque[MQTTDiscoveryPayload]
    unsub: CALLBACK_TYPE


class MqttOriginInfo(TypedDict, total=False):
    """Integration info of discovered entity."""

    name: str
    manufacturer: str
    sw_version: str
    hw_version: str
    support_url: str


class EntityTopicState:
    """Manage entity state write requests for subscribed topics."""

    def __init__(self) -> None:
        """Register topic."""
        self.subscribe_calls: dict[str, Entity] = {}

    @callback
    def process_write_state_requests(self, msg: MQTTMessage) -> None:
        """Process the write state requests."""
        while self.subscribe_calls:
            entity_id, entity = self.subscribe_calls.popitem()
            try:
                entity.async_write_ha_state()
            except ValueError as exc:
                _LOGGER.error(
                    "Value error while updating state of %s, topic: "
                    "'%s' with payload: %s: %s",
                    entity_id,
                    msg.topic,
                    msg.payload,
                    exc,
                )
            except Exception:
                _LOGGER.exception(
                    "Exception raised while updating state of %s, topic: "
                    "'%s' with payload: %s",
                    entity_id,
                    msg.topic,
                    msg.payload,
                )

    @callback
    def write_state_request(self, entity: Entity) -> None:
        """Register write state request."""
        self.subscribe_calls[entity.entity_id] = entity


@dataclass
class MqttData:
    """Keep the MQTT entry data."""

    client: MQTT
    config: list[ConfigType]
    data_config_flow_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Attribute `discovery_discovered_and_disabled` maps a discovery hash to
    # the entity registry index, which is a tuple (entity_platform, "mqtt", unique_id)
    # It allows to cleanup disabled entities when an empty payload is received.
    discovery_discovered_and_disabled: dict[tuple[str, str], tuple[str, str, str]] = (
        field(default_factory=dict)
    )
    discovery_already_discovered: set[tuple[str, str]] = field(default_factory=set)
    discovery_pending_discovered: dict[tuple[str, str], PendingDiscovered] = field(
        default_factory=dict
    )
    discovery_registry_hooks: dict[tuple[str, str], CALLBACK_TYPE] = field(
        default_factory=dict
    )
    discovery_unsubscribe: list[CALLBACK_TYPE] = field(default_factory=list)
    integration_unsubscribe: dict[str, CALLBACK_TYPE] = field(default_factory=dict)
    last_discovery: float = 0.0
    platforms_loaded: set[Platform | str] = field(default_factory=set)
    reload_dispatchers: list[CALLBACK_TYPE] = field(default_factory=list)
    reload_handlers: dict[str, CALLBACK_TYPE] = field(default_factory=dict)
    reload_schema: dict[str, VolSchemaType] = field(default_factory=dict)
    state_write_requests: EntityTopicState = field(default_factory=EntityTopicState)
    subscriptions_to_restore: set[Subscription] = field(default_factory=set)
    tags: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class MqttComponentConfig:
    """(component, object_id, node_id, discovery_payload)."""

    component: str
    object_id: str
    node_id: str | None
    discovery_payload: MQTTDiscoveryPayload


class DeviceMqttOptions(TypedDict, total=False):
    """Hold the shared MQTT specific options for an MQTT device."""

    qos: int


class MqttDeviceData(TypedDict, total=False):
    """Hold the data for an MQTT device."""

    name: str
    identifiers: list[str]
    connections: list[list[str]]
    configuration_url: str
    sw_version: str
    hw_version: str
    model: str
    model_id: str
    mqtt_settings: DeviceMqttOptions


class MqttAvailabilityData(TypedDict, total=False):
    """Hold the availability configuration for a device."""

    availability_topic: str
    availability_template: str
    payload_available: str
    payload_not_available: str


class MqttSubentryData(TypedDict, total=False):
    """Hold the data for an MQTT subentry."""

    device: MqttDeviceData
    components: dict[str, dict[str, Any]]
    availability: MqttAvailabilityData


DATA_MQTT: HassKey[MqttData] = HassKey("locknalert_mqtt")
DATA_MQTT_AVAILABLE: HassKey[asyncio.Future[bool]] = HassKey(
    "locknalert_mqtt_client_available"
)
