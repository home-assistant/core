"""Base entity classes for the HEMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Literal

from pyhems import CONTROLLER_INSTANCE, ESV_SETC, Frame, Property
from pyhems.definitions import EntityDefinition

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EchonetLiteCoordinator
from .types import EchonetLiteConfigEntry, EchonetLiteNodeState

_LOGGER = logging.getLogger(__name__)

# Platform type for entity classification
type PlatformType = Literal["binary"]


def infer_platform(entity: EntityDefinition) -> PlatformType | None:
    """Infer the platform type from entity definition.

    Args:
        entity: Entity definition to analyze.

    Returns:
        Platform type: "binary" or None for unsupported types.
    """
    if entity.enum_values:
        # Has enum values -> binary (2 values only)
        return "binary" if len(entity.enum_values) == 2 else None
    # Numeric entities not supported (sensor platform removed)
    return None


class EchonetLiteEntity(CoordinatorEntity[EchonetLiteCoordinator]):
    """Base entity bound to an ECHONET Lite node."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EchonetLiteCoordinator,
        node: EchonetLiteNodeState,
    ) -> None:
        """Initialize the base entity for the given device key."""

        super().__init__(coordinator)
        self._node = node

        # Build device_info once; sources are immutable after node creation
        manufacturer: str | None = None
        if node.manufacturer_code is not None:
            manufacturer = f"0x{node.manufacturer_code:06X}"
        name = node.product_code or f"ECHONET Lite node {node.device_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node.device_key)},
            name=name,
            manufacturer=manufacturer,
            model=node.product_code,
            serial_number=node.serial_number,
        )

    async def _async_send_property(self, epc: int, value: bytes) -> None:
        """Send a SetC request for a single EPC/value pair.

        Args:
            epc: ECHONET Property Code
            value: Property Data Content (EDT)
        """
        await self._async_send_properties(properties=[Property(epc=epc, edt=value)])

    async def _async_send_properties(self, properties: list[Property]) -> None:
        """Send a SetC request for multiple EPC/value pairs.

        Args:
            properties: List of Property objects to send
        """
        node = self._node
        frame = Frame(
            seoj=CONTROLLER_INSTANCE,
            deoj=node.eoj,
            esv=ESV_SETC,
            properties=properties,
        )
        try:
            sent = await self.coordinator.client.async_send(node.node_id, frame)
            if not sent:
                raise HomeAssistantError("The target node address is unknown")
        except OSError as err:
            raise HomeAssistantError(
                f"Failed to send ECHONET Lite command: {err!s}"
            ) from err

        # After a Set operation, schedule an earlier poll so the UI reflects the
        # updated device state sooner.
        if runtime_data := self.coordinator.config_entry.runtime_data:
            runtime_data.property_poller.schedule_immediate_poll(node.device_key)


@dataclass(frozen=True, kw_only=True)
class EchonetLiteEntityDescription(EntityDescription):
    """Base entity description for ECHONET Lite entities with common fields.

    This class provides common ECHONET-related fields and methods for all
    entity descriptions. Platform-specific descriptions should inherit from both
    this class and the appropriate platform EntityDescription using diamond
    inheritance:

        class EchonetLiteSwitchEntityDescription(SwitchEntityDescription, EchonetLiteEntityDescription):
            ...

    The diamond inheritance pattern works correctly because both this class and
    platform-specific EntityDescriptions inherit from EntityDescription, and
    Python's MRO resolves the inheritance properly with kw_only=True.
    """

    class_code: int
    """ECHONET Lite class code (class group + class code)."""
    epc: int
    """ECHONET Property Code."""
    require_write: bool | None = None
    """Write access requirement: None=don't care, True=must be writable, False=must NOT be writable."""
    manufacturer_code: int | None = None
    """Required manufacturer code for vendor-specific entities (None = all)."""
    fallback_name: str | None = None
    """Fallback name for user-defined entities without translation."""

    def should_create(self, node: EchonetLiteNodeState) -> bool:
        """Check if entity should be created for this node.

        Args:
            node: The node state to check against.

        Returns:
            True if the entity should be created for this node.
        """
        if self.epc not in node.get_epcs:
            return False
        if self.require_write is not None:
            if self.require_write != (self.epc in node.set_epcs):
                return False
        if self.manufacturer_code is not None:
            return node.manufacturer_code == self.manufacturer_code
        return True


class EchonetLiteDescribedEntity[DescriptionT: EchonetLiteEntityDescription](
    EchonetLiteEntity
):
    """Base class for ECHONET Lite entities with EntityDescription.

    This intermediate class handles the common initialization pattern shared by
    the switch platform. It extracts the
    repetitive __init__ logic that sets up unique_id, translation_key/name,
    and epc from the entity description.

    The `description` attribute provides type-safe access to the entity
    description with the correct generic type, avoiding mypy conflicts with
    platform base classes that define `entity_description`.
    """

    description: DescriptionT
    _epc: int

    def __init__(
        self,
        coordinator: EchonetLiteCoordinator,
        node: EchonetLiteNodeState,
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
        assert description.should_create(node), (
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


def setup_echonet_lite_platform[DescriptionT: EchonetLiteEntityDescription](
    entry: EchonetLiteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    platform_type: PlatformType,
    description_factory: Callable[[int, EntityDefinition], DescriptionT],
    entity_factory: Callable[
        [EchonetLiteCoordinator, EchonetLiteNodeState, DescriptionT], Entity
    ],
    platform_name: str,
) -> None:
    """Set up common entity platform setup pattern for ECHONET Lite.

    This helper handles:
    - Retrieving entity definitions from the definitions registry
    - Building entity descriptions from definitions (filtered by platform_type)
    - Creating entities for existing devices
    - Subscribing to coordinator updates for new device discovery
    - Logging skipped entities for debugging

    Args:
        entry: The config entry
        async_add_entities: Callback to add entities
        platform_type: Type of platform ("binary")
        description_factory: Factory function to create descriptions from definitions.
            Args: (class_code, entity_def)
        entity_factory: Factory function to create entity instances
        platform_name: Name of the platform for logging (e.g., "switch")

    """
    runtime_data = entry.runtime_data
    assert runtime_data is not None
    coordinator = runtime_data.coordinator
    definitions = runtime_data.definitions

    # Build descriptions from entity definitions, filtering by platform
    descriptions_by_class_code: dict[int, list[DescriptionT]] = {}
    for class_code, entity_defs in definitions.entities.items():
        descriptions_by_class_code[class_code] = [
            description_factory(class_code, entity_def)
            for entity_def in entity_defs
            if infer_platform(entity_def) == platform_type
        ]

    @callback
    def _async_add_entities_for_devices(device_keys: set[str]) -> None:
        """Create entities for the given device keys."""
        new_entities: list[Entity] = []

        for device_key in device_keys:
            node = coordinator.data.get(device_key)
            if not node:
                continue

            for description in descriptions_by_class_code.get(node.eoj.class_code, []):
                if not description.should_create(node):
                    _LOGGER.debug(
                        "Skipping %s %s for %s: EPC 0x%02X not meeting criteria",
                        platform_name,
                        description.key,
                        device_key,
                        description.epc,
                    )
                    continue
                new_entities.append(entity_factory(coordinator, node, description))

        if new_entities:
            async_add_entities(new_entities)

    @callback
    def _async_process_coordinator_update() -> None:
        """Handle coordinator updates - add entities for newly discovered devices."""
        if coordinator.new_device_keys:
            _async_add_entities_for_devices(coordinator.new_device_keys)

    entry.async_on_unload(
        coordinator.async_add_listener(_async_process_coordinator_update)
    )
    # Initial setup: create entities for all existing devices
    _async_add_entities_for_devices(set(coordinator.data.keys()))
