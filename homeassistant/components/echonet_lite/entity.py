"""Base entity classes for the HEMS Echonet Lite integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import Literal

from pyhems import EntityDefinition, NodeState, Property

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_EPC, DOMAIN, RUNTIME_MONITOR_MAX_SILENCE
from .coordinator import EchonetLiteCoordinator
from .types import EchonetLiteConfigEntry

_LOGGER = logging.getLogger(__name__)

# Platform type for entity classification
type PlatformType = Literal["switch"]


def can_process_enum_values(entity: EntityDefinition) -> bool:
    """Check if entity's enum_values can be automatically processed.

    Enum values must have unique keys for automatic processing.
    Entities with duplicate keys cannot be reliably mapped and are
    excluded from platform creation and string generation.

    Args:
        entity: Entity definition to check.

    Returns:
        True if enum_values can be processed, False otherwise.
    """
    if not entity.enum_values:
        return True  # Numeric entities are always processable

    keys = set()
    for enum_val in entity.enum_values:
        if enum_val.key in keys:
            return False
        keys.add(enum_val.key)

    return True


def infer_platform(entity: EntityDefinition) -> PlatformType | None:
    """Infer the platform type from entity definition using MRA get/set info.

    Decision matrix:
        | Data shape        | writable (set != notApplicable) |
        |-------------------|--------------------------------|
        | 2 enum values     | switch                         |
        | other             | None (skip)                    |

    Args:
        entity: Entity definition to analyze.

    Returns:
        Platform type string, or None if entity should be skipped.
    """
    if (
        entity.get != "notApplicable"
        and entity.set != "notApplicable"
        and entity.enum_values
        and len(entity.enum_values) == 2
    ):
        return "switch"
    return None


class EchonetLiteEntity(CoordinatorEntity[EchonetLiteCoordinator]):
    """Base entity bound to an ECHONET Lite node."""

    _attr_has_entity_name = True

    # Threshold after which a lack of runtime activity marks the entity
    # as unavailable. Matches the inactivity repair issue threshold so
    # UI availability and the repair issue rise/fall together.
    _runtime_silence_threshold: float = RUNTIME_MONITOR_MAX_SILENCE.total_seconds()

    def __init__(
        self,
        coordinator: EchonetLiteCoordinator,
        node: NodeState,
    ) -> None:
        """Initialize the base entity for the given device key."""

        super().__init__(coordinator)
        self._node = node

        # Build device_info once; sources are immutable after node creation
        manufacturer: str | None = None
        if node.manufacturer_code is not None:
            manufacturer = (
                node.manufacturer_name_en or f"0x{node.manufacturer_code:06X}"
            )
        name = node.product_code or f"ECHONET Lite node {node.device_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node.device_key)},
            name=name,
            manufacturer=manufacturer,
            model=node.product_code,
            serial_number=node.serial_number,
        )

    @property
    def available(self) -> bool:
        """Return True if the underlying runtime is still receiving activity.

        Falls back to ``CoordinatorEntity.available`` first so disabled
        coordinators still mark entities unavailable. Additionally, if the
        runtime has been silent for longer than ``RUNTIME_MONITOR_MAX_SILENCE``,
        the entity is reported as unavailable even while the coordinator
        itself is considered healthy.
        """
        if not super().available:
            return False
        last_activity_at = self.coordinator.last_runtime_activity_at
        if last_activity_at is None:
            # No baseline yet: rely on the coordinator's own availability.
            return True
        return time.monotonic() - last_activity_at < self._runtime_silence_threshold

    async def _async_send_property(self, epc: int, value: bytes) -> None:
        """Send a SetC request for a single EPC/value pair.

        Args:
            epc: ECHONET Property Code
            value: Property Data Content (EDT)

        Raises:
            HomeAssistantError: If the EPC is not writable by the device.
        """
        await self._async_send_properties(properties=[Property(epc=epc, edt=value)])

    async def _async_send_properties(self, properties: list[Property]) -> None:
        """Send a SetC request for multiple EPC/value pairs.

        Args:
            properties: List of Property objects to send

        Raises:
            HomeAssistantError: If any EPC is not writable by the device.
        """
        node = self._node
        not_writable = [
            prop.epc for prop in properties if prop.epc not in node.set_epcs
        ]
        if not_writable:
            hex_list = ", ".join(f"0x{epc:02X}" for epc in not_writable)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="epc_not_writable",
                translation_placeholders={"epc_list": hex_list},
            )
        sent = await self.coordinator.config_entry.runtime_data.client.set_properties(
            node_id=node.node_id,
            deoj=node.eoj,
            properties=properties,
        )
        if not sent:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="target_node_unknown",
            )

        # After a Set operation, schedule an earlier poll so the UI reflects the
        # updated device state sooner.
        self.coordinator.config_entry.runtime_data.property_poller.schedule_immediate_poll(
            node.device_key
        )


@dataclass(frozen=True, kw_only=True)
class EchonetLiteEntityDescription(EntityDescription):
    """Base entity description for ECHONET Lite entities with common fields.

    This class provides common ECHONET-related fields and methods for all
    entity descriptions. Platform-specific descriptions should inherit from both
    this class and the appropriate platform EntityDescription using diamond
    inheritance:

        class EchonetLiteSensorEntityDescription(SensorEntityDescription, EchonetLiteEntityDescription):
            ...

    The diamond inheritance pattern works correctly because both this class and
    platform-specific EntityDescriptions inherit from EntityDescription, and
    Python's MRO resolves the inheritance properly with kw_only=True.
    """

    class_code: int
    """ECHONET Lite class code (class group + class code)."""
    epc: int
    """ECHONET Property Code."""
    manufacturer_code: int | None = None
    """Required manufacturer code for vendor-specific entities (None = all)."""
    fallback_name: str | None = None
    """Fallback name for user-defined entities without translation."""

    def should_create(self, node: NodeState) -> bool:
        """Check if entity should be created for this node.

        Args:
            node: The node state to check against.

        Returns:
            True if the entity should be created for this node.
        """
        # Check if EPC is available in either GET or SET property map
        # (write-only button entities are only in set_epcs)
        if self.epc not in node.get_epcs and self.epc not in node.set_epcs:
            return False
        if self.manufacturer_code is not None:
            return node.manufacturer_code == self.manufacturer_code
        return True


class EchonetLiteDescribedEntity[DescriptionT: EchonetLiteEntityDescription](
    EchonetLiteEntity
):
    """Base class for ECHONET Lite entities with EntityDescription.

    This intermediate class handles the common initialization pattern shared by
    binary_sensor, sensor, select, and switch platforms. It extracts the
    repetitive __init__ logic that sets up unique_id, translation_key/name,
    and epc from the entity description.

    Climate entities should inherit from EchonetLiteEntity directly since they manage
    multiple EPCs and don't use the standard EntityDescription pattern.

    The `description` attribute provides type-safe access to the entity
    description with the correct generic type, avoiding mypy conflicts with
    platform base classes that define `entity_description`.
    """

    description: DescriptionT
    _epc: int

    def __init__(
        self,
        coordinator: EchonetLiteCoordinator,
        node: NodeState,
        description: DescriptionT,
    ) -> None:
        """Initialize a described ECHONET Lite entity.

        Args:
            coordinator: The data update coordinator.
            node: The node state for this entity.
            description: The entity description with EPC metadata.

        Raises:
            AssertionError: If description.should_create(node) returns False.
        """
        if not description.should_create(node):
            raise ValueError(
                f"Entity created for EPC 0x{description.epc:02X} "
                "that doesn't meet creation criteria"
            )
        super().__init__(coordinator, node)
        self.description = description
        self.entity_description = description  # HA standard attribute
        self._attr_unique_id = f"{node.device_key}-{description.key}"
        # Use translation_key if available, otherwise use fallback_name
        if description.translation_key:
            self._attr_translation_key = description.translation_key
        elif description.fallback_name:
            self._attr_name = description.fallback_name
        self._epc = description.epc

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes exposing the ECHONET Property Code."""
        return {ATTR_EPC: f"0x{self._epc:02X}"}


def setup_echonet_lite_platform[DescriptionT: EchonetLiteEntityDescription](
    entry: EchonetLiteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    platform_type: PlatformType,
    description_factory: Callable[[int, EntityDefinition], DescriptionT],
    entity_factory: Callable[[EchonetLiteCoordinator, NodeState, DescriptionT], Entity],
    platform_name: str,
) -> None:
    """Set up common entity platform setup pattern for ECHONET Lite.

    This helper handles:
    - Retrieving entity definitions from the definitions registry
    - Building entity descriptions from definitions (filtered by platform_type)
    - Creating entities for existing devices
    - Subscribing to device-added notifications for new device discovery
    - Logging skipped entities for debugging

    Args:
        entry: The config entry
        async_add_entities: Callback to add entities
        platform_type: Type of platform (e.g. "switch")
        description_factory: Factory function to create descriptions from definitions.
            Args: (class_code, entity_def)
        entity_factory: Factory function to create entity instances
        platform_name: Name of the platform for logging (e.g., "switch")

    """
    runtime_data = entry.runtime_data
    definitions = runtime_data.definitions

    # Build descriptions from entity definitions, filtering by platform
    descriptions_by_class_code: dict[int, list[DescriptionT]] = {}
    for class_code, entity_defs in definitions.entities.items():
        descriptions_by_class_code[class_code] = [
            description_factory(class_code, entity_def)
            for entity_def in entity_defs
            if infer_platform(entity_def) == platform_type
            and can_process_enum_values(entity_def)
            and not (entity_def.set != "notApplicable" and entity_def.byte_offset > 0)
        ]

    @callback
    def _entity_factory(
        coordinator: EchonetLiteCoordinator, node: NodeState
    ) -> list[Entity]:
        entities: list[Entity] = []
        for description in descriptions_by_class_code.get(node.eoj.class_code, []):
            if not description.should_create(node):
                _LOGGER.debug(
                    "Skipping %s %s for %s: EPC 0x%02X not meeting criteria",
                    platform_name,
                    description.key,
                    node.device_key,
                    description.epc,
                )
                continue
            entities.append(entity_factory(coordinator, node, description))
        return entities

    setup_echonet_lite_device_platform(
        entry,
        async_add_entities,
        entity_factory=_entity_factory,
    )


def setup_echonet_lite_device_platform(
    entry: EchonetLiteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    *,
    entity_factory: Callable[[EchonetLiteCoordinator, NodeState], list[Entity]],
) -> None:
    """Set up a platform that emits zero or more entities per discovered device.

    The ``entity_factory`` receives a node and returns the list of entities
    to create for it (empty list if the node is not handled by this platform).
    This is the generic building block used both by description-driven
    platforms (via ``setup_echonet_lite_platform``) and by platforms that
    create one dedicated entity per matching class code (climate, fan).

    Args:
        entry: The config entry
        async_add_entities: Callback to add entities
        entity_factory: Callable building entities for a given node.
    """
    coordinator = entry.runtime_data.coordinator

    @callback
    def _async_add_entities_for_device(device_key: str) -> None:
        node = coordinator.data.get(device_key)
        if not node:
            return
        if entities := entity_factory(coordinator, node):
            async_add_entities(entities)

    entry.async_on_unload(
        coordinator.async_add_device_added_listener(_async_add_entities_for_device)
    )
    # Initial setup: create entities for all existing devices
    for device_key in coordinator.data:
        _async_add_entities_for_device(device_key)
