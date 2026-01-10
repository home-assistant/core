"""Definitions loader for the ECHONET Lite integration.

This module loads entity definitions from definitions.json which contains
MRA-based and vendor definitions (generated at build time by generate_definitions.py).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Literal

_LOGGER = logging.getLogger(__name__)


class DefinitionsLoadError(Exception):
    """Raised when definitions.json cannot be loaded.

    This is a fatal error - the ECHONET Lite integration cannot function
    without the device definitions file.
    """


# Path to generated definitions file (includes MRA + vendor definitions)
DEFINITIONS_FILE = Path(__file__).parent / "definitions.json"


@dataclass(frozen=True, slots=True)
class EntityDefinition:
    """Definition of an entity to create for a device.

    The `translation_key` and `fallback_name` fields are computed during
    construction to centralize common entity description logic.
    """

    platform: str
    epc: int
    translation_key: str | None  # None if not translatable
    device_class: str
    unit: str
    state_class: str
    decoder: str
    name_en: str
    name_ja: str
    enum_values: dict[str, str]
    fallback_name: str | None  # Display name when translation_key is None
    byte_offset: int = 0  # Byte position in EDT (0-indexed)
    byte_count: int = 1  # Number of bytes to read
    manufacturer_code: int | None = None  # Required manufacturer code (None = all)


@dataclass(frozen=True, slots=True)
class DeviceDefinition:
    """Definition of an ECHONET Lite device class."""

    class_code: int
    name_en: str
    name_ja: str
    entities: tuple[EntityDefinition, ...]


@dataclass(frozen=True, slots=True)
class BinaryDecoderSpec:
    """Specification for decoding binary state EDT data.

    Guaranteed to have on/off values for state comparison and command generation.
    """

    on: bytes  # Required: e.g., b"\x30"
    off: bytes  # Required: e.g., b"\x31"

    def create_decoder(self) -> Callable[[bytes], bool | None]:
        """Create a binary decoder function from this spec.

        Returns:
            A function that decodes EDT bytes to a boolean.
        """

        def _binary_decoder(state: bytes) -> bool | None:
            return state == self.on if state else None

        return _binary_decoder


# Type alias for decoder specifications (only binary decoders for now)
DecoderSpec = BinaryDecoderSpec


# Platform type for entity definitions
type PlatformType = Literal["binary"]


@dataclass(frozen=True, slots=True)
class _PlatformData:
    """Internal data container for a platform type.

    Stores entity definitions already paired with their resolved decoders.
    All entities are guaranteed to have valid decoders.
    """

    resolved: dict[int, tuple[tuple[EntityDefinition, DecoderSpec], ...]]


@dataclass(frozen=True, slots=True)
class DefinitionsRegistry:
    """Registry of device definitions loaded from JSON.

    This is an immutable data container holding definitions loaded from
    definitions.json (MRA-based standard definitions + vendor definitions).

    Use load_definitions_registry() or async_get_definitions_registry() to create.
    """

    version: str
    mra_version: str
    decoders: dict[str, DecoderSpec]
    monitored_epcs: dict[int, frozenset[int]]
    _platforms: dict[PlatformType, _PlatformData]

    def get_binary_decoder(self, name: str) -> BinaryDecoderSpec | None:
        """Get a binary decoder specification for on/off values.

        Returns:
            BinaryDecoderSpec if found, None otherwise.
            Guaranteed to have on and off byte values.
        """
        spec = self.decoders.get(name)
        return spec if isinstance(spec, BinaryDecoderSpec) else None

    def get_resolved_entities(
        self, platform_type: PlatformType
    ) -> dict[int, tuple[tuple[EntityDefinition, DecoderSpec], ...]]:
        """Get entity definitions with resolved decoders for a platform type.

        Args:
            platform_type: Type of platform ("binary")

        Returns:
            Dictionary mapping class_code to tuples of (EntityDefinition, DecoderSpec).
            Guaranteed: all decoders are valid, no empty tuples.
        """
        return self._platforms[platform_type].resolved


# ---------------------------------------------------------------------------
# Definition loading functions
# ---------------------------------------------------------------------------


def _parse_hex_int(value: Any) -> int | None:
    """Parse an integer from various formats (int, hex string).

    Args:
        value: The value to parse (int, "0x..." string, or decimal string).

    Returns:
        Parsed integer or None if invalid.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            # Support both "0x..." hex and decimal strings
            return int(value, 16) if value.startswith(("0x", "0X")) else int(value)
        except ValueError:
            return None
    return None


def _load_definitions_json() -> dict[str, Any]:
    """Load definitions from the JSON file.

    Returns:
        Parsed JSON data.

    Raises:
        DefinitionsLoadError: If the file cannot be loaded.
    """
    if not DEFINITIONS_FILE.exists():
        raise DefinitionsLoadError(
            f"Device definitions file not found: {DEFINITIONS_FILE}"
        )

    try:
        with DEFINITIONS_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as ex:
        raise DefinitionsLoadError(f"Failed to load device definitions: {ex}") from ex


def _parse_decoder_spec(name: str, spec: dict[str, Any]) -> DecoderSpec:
    """Parse a single decoder specification.

    Args:
        name: Decoder name for error messages.
        spec: Decoder specification dictionary.

    Returns:
        DecoderSpec instance.

    Raises:
        AssertionError: If the decoder specification is invalid.
    """
    decoder_type = spec.get("type", "binary")

    assert decoder_type == "binary", (
        f"Unknown decoder type '{decoder_type}' for '{name}'"
    )

    on_value = spec.get("on")
    off_value = spec.get("off")
    assert on_value is not None and off_value is not None, (
        f"Binary decoder '{name}' missing on/off values"
    )
    return BinaryDecoderSpec(on=bytes([on_value]), off=bytes([off_value]))


def _load_decoders(decoders_data: dict[str, Any]) -> dict[str, DecoderSpec]:
    """Load decoder specifications from parsed JSON data.

    Args:
        decoders_data: Dictionary of decoder name to decoder spec.

    Returns:
        Dictionary of decoder name to DecoderSpec.
    """
    return {
        name: _parse_decoder_spec(name, spec) for name, spec in decoders_data.items()
    }


def _parse_entity(
    entity_data: dict[str, Any],
    class_code: int,
    source: str,
    *,
    require_translation: bool,
    manufacturer_code: int | None = None,
) -> EntityDefinition | None:
    """Parse a single entity definition.

    Args:
        entity_data: Entity definition dictionary.
        class_code: Device class code for logging.
        source: Source description for logging.
        require_translation: If True, require translation_key or name_en.
        manufacturer_code: Manufacturer code to set on entity.

    Returns:
        EntityDefinition or None if invalid.
    """
    # Parse EPC (support both integer and hex string formats)
    epc_raw = entity_data.get("epc")
    epc = epc_raw if isinstance(epc_raw, int) else _parse_hex_int(epc_raw)
    if epc is None:
        _LOGGER.warning(
            "Missing or invalid EPC in %s definition for class 0x%04X",
            source,
            class_code,
        )
        return None

    # Validate required fields
    decoder = entity_data.get("decoder", "")
    if not decoder:
        _LOGGER.warning("Missing decoder for EPC 0x%02X in %s definition", epc, source)
        return None

    translation_key_raw = entity_data.get("translation_key", "")
    name_en = entity_data.get("name_en", "")

    if require_translation and not translation_key_raw and not name_en:
        _LOGGER.warning(
            "EPC 0x%02X in %s definition requires translation_key or name_en",
            epc,
            source,
        )
        return None

    try:
        if manufacturer_code is None:
            manufacturer_code = entity_data.get("manufacturer_code")

        # Compute derived fields
        platform = entity_data.get("platform", "binary")
        byte_offset = entity_data.get("byte_offset", 0)
        translation_key: str | None = translation_key_raw or None
        fallback_name: str | None = name_en if not translation_key else None

        return EntityDefinition(
            platform=platform,
            epc=epc,
            translation_key=translation_key,
            device_class=entity_data.get("device_class", ""),
            unit=entity_data.get("unit", ""),
            state_class=entity_data.get("state_class", ""),
            decoder=decoder,
            name_en=name_en,
            name_ja=entity_data.get("name_ja", ""),
            enum_values=entity_data.get("enum_values", {}),
            fallback_name=fallback_name,
            byte_offset=byte_offset,
            byte_count=entity_data.get("byte_count", 1),
            manufacturer_code=manufacturer_code,
        )
    except (KeyError, TypeError) as err:
        _LOGGER.warning(
            "Invalid entity definition for EPC 0x%02X in %s: %s", epc, source, err
        )
        return None


def _parse_entity_list(
    entities_data: list[Any],
    class_code: int,
    source: str,
    *,
    require_translation: bool,
    manufacturer_code: int | None = None,
) -> list[EntityDefinition]:
    """Parse a list of entity definitions.

    Args:
        entities_data: List of entity definition dicts.
        class_code: Device class code for logging.
        source: Source description for logging.
        require_translation: If True, require translation_key or name_en.
        manufacturer_code: Manufacturer code to set on entities (for vendor defs).

    Returns:
        List of successfully parsed EntityDefinition objects.
    """
    return [
        entity
        for entity_data in entities_data
        if isinstance(entity_data, dict)
        and (
            entity := _parse_entity(
                entity_data,
                class_code,
                source,
                require_translation=require_translation,
                manufacturer_code=manufacturer_code,
            )
        )
        is not None
    ]


def _load_devices(devices_data: dict[str, Any]) -> dict[int, DeviceDefinition]:
    """Load device definitions from parsed JSON data.

    Args:
        devices_data: Dictionary of class_code to device data.

    Returns:
        Dictionary of class_code to DeviceDefinition.
    """
    devices: dict[int, DeviceDefinition] = {}

    for class_code_key, device_data in devices_data.items():
        try:
            class_code = int(class_code_key)
        except ValueError:
            continue

        entities = _parse_entity_list(
            device_data.get("entities", []),
            class_code,
            source="definitions.json",
            require_translation=False,
        )

        devices[class_code] = DeviceDefinition(
            class_code=class_code,
            name_en=device_data.get("name_en", ""),
            name_ja=device_data.get("name_ja", ""),
            entities=tuple(entities),
        )

    return devices


def _build_platform_data(
    devices: dict[int, DeviceDefinition],
    decoders: dict[str, DecoderSpec],
) -> tuple[
    dict[int, frozenset[int]],
    dict[PlatformType, _PlatformData],
]:
    """Build monitored EPCs and platform data from loaded definitions.

    Entities without a valid decoder for their platform type are filtered out
    with a warning. This ensures all returned entities have valid decoders.

    Args:
        devices: Device definitions from definitions.json.
        decoders: Decoder specifications.

    Returns:
        Tuple of (monitored_epcs, platforms).
    """
    # Platform to decoder type mapping
    platform_decoder_types: dict[PlatformType, type[DecoderSpec]] = {
        "binary": BinaryDecoderSpec,
    }
    # Initialize all platforms with resolved entities
    resolved_by_platform: dict[
        PlatformType, dict[int, list[tuple[EntityDefinition, DecoderSpec]]]
    ] = {
        "binary": {},
    }

    def add_entity(class_code: int, entity: EntityDefinition) -> None:
        """Add entity to appropriate platform bucket if decoder is valid."""
        platform = entity.platform
        if platform not in platform_decoder_types:
            return

        # platform is already validated as a valid PlatformType key
        platform_key: PlatformType = platform  # type: ignore[assignment]
        expected_type = platform_decoder_types[platform_key]
        decoder = decoders.get(entity.decoder)

        assert decoder is not None, (
            f"Entity EPC 0x{entity.epc:02X} for class 0x{class_code:04X} "
            f"has unknown decoder '{entity.decoder}'"
        )

        assert isinstance(decoder, expected_type), (
            f"Entity EPC 0x{entity.epc:02X} for class 0x{class_code:04X} "
            f"has decoder '{entity.decoder}' of wrong type "
            f"(expected {expected_type.__name__}, got {type(decoder).__name__})"
        )

        resolved_by_platform[platform_key].setdefault(class_code, []).append(
            (entity, decoder)
        )

    # Add entities from definitions.json (MRA + vendor definitions)
    for class_code, device in devices.items():
        for entity in device.entities:
            add_entity(class_code, entity)

    # Build monitored_epcs from resolved entities (only valid entities)
    epcs_by_class: dict[int, set[int]] = {}
    for by_class in resolved_by_platform.values():
        for class_code, entity_list in by_class.items():
            epcs_by_class.setdefault(class_code, set()).update(
                entity.epc for entity, _ in entity_list
            )

    # Convert to immutable structures
    monitored_epcs = {cc: frozenset(epcs) for cc, epcs in epcs_by_class.items()}
    platforms: dict[PlatformType, _PlatformData] = {
        platform: _PlatformData(
            resolved={cc: tuple(ents) for cc, ents in by_class.items()}
        )
        for platform, by_class in resolved_by_platform.items()
    }

    return monitored_epcs, platforms


def load_definitions_registry() -> DefinitionsRegistry:
    """Load and create a DefinitionsRegistry.

    Loads definitions from definitions.json (MRA-based + vendor definitions).

    Returns:
        Populated DefinitionsRegistry instance.

    Raises:
        DefinitionsLoadError: If definitions.json cannot be loaded.
    """
    data = _load_definitions_json()

    version = data.get("version", "unknown")
    mra_version = data.get("mra_version", "unknown")
    decoders = _load_decoders(data.get("decoders", {}))
    devices = _load_devices(data.get("devices", {}))

    _LOGGER.debug(
        "Loaded %d device definitions (MRA version: %s)", len(devices), mra_version
    )

    monitored_epcs, platforms = _build_platform_data(devices, decoders)

    return DefinitionsRegistry(
        version=version,
        mra_version=mra_version,
        decoders=decoders,
        monitored_epcs=monitored_epcs,
        _platforms=platforms,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def async_get_definitions_registry() -> DefinitionsRegistry:
    """Load the definitions registry asynchronously.

    This runs the synchronous load in an executor to avoid
    blocking the event loop.

    Returns:
        DefinitionsRegistry instance (not cached - reloads each time).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, load_definitions_registry)
