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
    """Batch and drain HA entity state-write requests triggered by MQTT messages.

    Each time a message arrives on a subscribed topic, one or more entities may
    need their HA state updated.  Rather than writing state immediately inside
    the per-subscription callback (which runs inside the paho message handler),
    entities register a pending write here, and :meth:`process_write_state_requests`
    drains the batch once per message after all callbacks have run.
    """

    def __init__(self) -> None:
        """Initialise with an empty pending-write registry."""
        self.subscribe_calls: dict[str, Entity] = {}

    @callback
    def process_write_state_requests(self, msg: MQTTMessage) -> None:
        """Drain all pending state-write requests triggered by *msg*.

        Called once per incoming MQTT message after all subscription callbacks
        have run.  Each registered entity has ``async_write_ha_state`` called;
        errors are logged and do not abort processing of remaining entities.

        Args:
            msg (MQTTMessage): The paho MQTT message that triggered the writes,
                used only for diagnostic logging when a write fails.
        """
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
        """Register *entity* for a deferred state write.

        The write is not performed immediately; it is deferred until
        :meth:`process_write_state_requests` is called for the current message.
        Registering the same entity twice before the batch is drained is safe —
        the dict keyed by entity_id is idempotent.

        Args:
            entity (Entity): The entity whose HA state should be written after
                the current message has been fully processed.
        """
        self.subscribe_calls[entity.entity_id] = entity


@dataclass
class MqttData:
    """Runtime state for a single locknalert_mqtt config entry.

    Stored in ``hass.data[DATA_MQTT]`` and shared by all modules that need
    access to the MQTT client, discovery state, or reload machinery.

    Attributes:
        client (MQTT): The HA-aware MQTT client connected to the bridge.
        config (list[ConfigType]): Parsed YAML configuration items for this
            entry (``locknalert_mqtt:`` section from ``configuration.yaml``).
        data_config_flow_lock (asyncio.Lock): Prevents concurrent config-flow
            operations that touch shared entry data.
        discovery_discovered_and_disabled (dict): Maps a discovery hash to an
            entity registry index tuple for disabled-entity cleanup.
        discovery_already_discovered (set): Discovery hashes that have
            already been processed and are considered active.
        discovery_pending_discovered (dict): Discovery hashes that have been
            seen but whose setup is not yet complete.
        discovery_registry_hooks (dict): Cancellable entity-registry hooks
            registered during discovery, keyed by discovery hash.
        discovery_unsubscribe (list[CALLBACK_TYPE]): Cancellables for the
            MQTT discovery topic subscriptions.
        integration_unsubscribe (dict[str, CALLBACK_TYPE]): Integration-level
            MQTT topic subscriptions that are not tied to specific entities.
        last_discovery (float): ``time.monotonic()`` timestamp of the most
            recent discovery message, used for cooldown calculations.
        platforms_loaded (set): Platform names that have been forwarded and
            set up via the config entry.
        reload_dispatchers (list[CALLBACK_TYPE]): Cancellables for update
            listeners and discovery dispatchers registered during setup.
        reload_handlers (dict[str, CALLBACK_TYPE]): Per-platform reload
            callbacks invoked when the YAML configuration is reloaded.
        reload_schema (dict[str, VolSchemaType]): Per-platform validation
            schemas used when reloading YAML configuration.
        state_write_requests (EntityTopicState): Batches deferred entity
            state writes triggered by incoming MQTT messages.
        subscriptions_to_restore (set[Subscription]): Subscriptions saved
            during unload so they can be reinstated on reload.
        tags (dict): Arbitrary per-device tag data indexed by device identifier.
    """

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
    """Parsed component descriptor extracted from an MQTT discovery message.

    Attributes:
        component (str): Platform name, e.g. ``"alarm_control_panel"``.
        object_id (str): Unique object identifier within the component.
        node_id (str | None): Optional node (device) identifier that prefixes
            the discovery topic; ``None`` when the topic has no node segment.
        discovery_payload (MQTTDiscoveryPayload): The full discovery payload
            dict from which this component config was extracted.
    """

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
