#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "pydantic",
#   "pyyaml",
#   "pyhems",
# ]
# ///
# ruff: noqa: T201
"""Generate ECHONET Lite definitions from MRA data.

This script:
1. Downloads MRA data using pyhems.MRAFetcher
2. Parses MRA JSON to extract device and property specifications
3. Merges vendor-specific definitions from echonet_lite_custom_definitions.yaml
4. Generates definitions.json for runtime entity creation
5. Updates strings.json with entity translation keys

Run with: uv run homeassistant/components/echonet_lite/generator/generate_definitions.py

Input files:
- generator/strings_static.json (static strings for config, options, issues)
- generator/echonet_lite_custom_definitions.yaml (vendor-specific entity definitions)

Output files:
- homeassistant/components/echonet_lite/definitions.json
- homeassistant/components/echonet_lite/strings.json (entity section updated)

Note: Translations (translations/*.json) are managed by Lokalise and should not
be committed. Only strings.json (English base) is version controlled.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, Field
from pyhems.mra_fetcher import MRAFetcher

# ============================================================================
# Constants
# ============================================================================

ECHONET_LITE_DIR = Path(__file__).parent.parent
GENERATOR_DIR = Path(__file__).parent
STRINGS_STATIC_FILE = GENERATOR_DIR / "strings_static.json"


# ============================================================================
# Pydantic Models
# ============================================================================


class BinaryDecoder(BaseModel):
    """Decoder configuration for binary on/off values."""

    type: Literal["binary"] = "binary"
    on: str
    off: str


DecoderConfig = BinaryDecoder


class MRAProperty(BaseModel):
    """Parsed MRA property data."""

    epc: int
    name_en: str = ""
    name_ja: str = ""
    get: bool = False
    data_type: str | None = None
    mra_format: str | None = None  # e.g., "uint16", "int8"
    mra_unit: str | None = None  # e.g., "W", "Wh", "Celsius"
    mra_minimum: float | None = None
    mra_maximum: float | None = None
    mra_multiple_of: float | None = None  # scale factor, e.g., 0.1 for tenths
    enum_values: dict[str, str] = Field(default_factory=dict)
    enum_descriptions: dict[str, str] = Field(default_factory=dict)


class EntityConfig(BaseModel):
    """Configuration for a generated entity."""

    platform: str
    epc: str
    name_en: str = ""
    name_ja: str = ""
    device_class: str = ""
    unit: str = ""
    state_class: str = ""
    decoder: str = ""
    enum_values: dict[str, str] = Field(default_factory=dict)
    enum_descriptions: dict[str, str] = Field(default_factory=dict)
    translation_key: str = ""


class DeviceDefinition(BaseModel):
    """Definition of a device class."""

    name_en: str = ""
    name_ja: str = ""
    entities: list[EntityConfig] = Field(default_factory=list)


class GeneratedDefinitions(BaseModel):
    """Complete generated definitions output."""

    version: str = "1.0.0"
    mra_version: str = "unknown"
    devices: dict[str, DeviceDefinition] = Field(default_factory=dict)
    common: list[EntityConfig] = Field(default_factory=list)
    decoders: dict[str, dict[str, Any]] = Field(default_factory=dict)


# ============================================================================
# Utility Functions
# ============================================================================


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case for translation keys.

    Home Assistant requires translation keys to match [a-z0-9-_]+.
    """
    # Insert underscore before uppercase letters (except at start)
    s1 = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    # Convert to lowercase
    return s1.lower()


def _parse_hex_int(value: Any) -> int | None:
    """Parse a hex string or int to integer.

    Args:
        value: String like "0x0135" or integer.

    Returns:
        Integer value or None if parsing fails.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)  # auto-detect base (0x for hex)
        except ValueError:
            return None
    return None


# ============================================================================
# Decoder Definitions
# ============================================================================

# Binary decoders are dynamically registered based on enum values
DECODERS: dict[str, dict[str, Any]] = {}


# ============================================================================
# EPC Mapping Definitions
# ============================================================================

# Common EPCs from superClass 0x0000 that are added to all device classes
# 0x80: Operation status (binary sensor)
COMMON_EPCS: frozenset[int] = frozenset({0x80})

# Binary entity device_class overrides
# Only EPC 0x80 (Operation status) has consistent meaning across all device classes.
# Other state-type EPCs are auto-generated by _try_state_entity without device_class.
BINARY_DEVICE_CLASS_OVERRIDES: dict[tuple[int | None, int], str] = {
    (None, 0x80): "power",  # Operation status - common to all device classes
}


# ============================================================================\n# MRA Parsing Functions\n# ============================================================================


def parse_mra_property(
    prop_data: dict[str, Any], definitions: dict[str, Any]
) -> MRAProperty:
    """Parse a single MRA property definition.

    Args:
        prop_data: MRA property data
        definitions: MRA definitions for resolving $ref

    Returns:
        Parsed MRAProperty
    """
    # MRA properties always have these required keys: epc, propertyName, accessRule, data
    epc = int(prop_data["epc"], 16)

    name_data = prop_data["propertyName"]
    name_en = name_data["en"]
    name_ja = name_data["ja"]

    # Parse access rules
    # "required", "required_c" (conditional), "optional" all mean accessible
    access = prop_data["accessRule"]
    get_val = access["get"]
    get_access = get_val in ("required", "required_c", "optional")

    # Parse data specification
    data_spec = prop_data["data"]

    # Collect all data specs to process (for oneOf, process all elements)
    data_specs_to_process: list[dict[str, Any]] = []
    if "oneOf" in data_spec:
        one_of = data_spec["oneOf"]
        if one_of and isinstance(one_of, list):
            data_specs_to_process.extend(one_of)
    else:
        data_specs_to_process.append(data_spec)

    # Resolve $ref and collect all resolved specs
    resolved_specs: list[dict[str, Any]] = []
    for spec in data_specs_to_process:
        if "$ref" in spec:
            ref = spec["$ref"]
            # $ref format: "#/definitions/state_Detected-NotDetected_4142"
            if ref.startswith("#/definitions/"):
                def_name = ref.replace("#/definitions/", "")
                if def_name in definitions:
                    resolved_specs.append(definitions[def_name])
        else:
            resolved_specs.append(spec)

    # Use first spec for primary type inference
    data_spec = resolved_specs[0] if resolved_specs else {}
    data_type = data_spec.get("type")

    # Extract numeric type info from MRA definition
    mra_format: str | None = None
    mra_unit: str | None = None
    mra_minimum: float | None = None
    mra_maximum: float | None = None
    mra_multiple_of: float | None = None

    if data_type == "number":
        # Extract format (uint8, uint16, uint32, int8, int16, int32)
        mra_format = data_spec.get("format")
        # Extract unit (W, Wh, kWh, Celsius, %, etc.)
        mra_unit = data_spec.get("unit")
        # Extract numeric range
        mra_minimum = data_spec.get("minimum")
        mra_maximum = data_spec.get("maximum")
        # Extract scale factor (MRA uses "multiple", JSON Schema uses "multipleOf")
        mra_multiple_of = data_spec.get("multiple") or data_spec.get("multipleOf")

    # Parse enum values from all specs (state type and level type)
    enum_values: dict[str, str] = {}
    enum_descriptions: dict[str, str] = {}

    for spec in resolved_specs:
        spec_type = spec.get("type")

        # Handle level type: e.g., {"type": "level", "base": "0x31", "maximum": 8}
        # Generates level 1 to maximum with EDT values starting from base
        if spec_type == "level":
            base = int(spec["base"], 16)
            maximum = spec["maximum"]
            # Skip multi-byte levels (base >= 256) - too complex for select
            if base >= 256:
                continue
            # Skip levels with too many values (> 32) - impractical for select UI
            if maximum > 32:
                continue
            for i in range(maximum):
                edt_decimal = str(base + i)
                level_num = i + 1
                translation_key_name = f"level_{level_num}"
                enum_values[edt_decimal] = translation_key_name
                enum_descriptions[translation_key_name] = f"Level {level_num}"
            # Update data_type to state for entity type determination
            data_type = "state"

        # Handle state type with enum
        elif spec_type == "state":
            for item in spec.get("enum", []):
                edt = item["edt"]
                val_name = item["name"]
                # Skip range values like "0x000a...0x0013" (not supported)
                if "..." in edt:
                    continue
                # Convert hex string to decimal string (e.g., "0x41" -> "65")
                edt_decimal = str(int(edt, 16))
                # Convert camelCase to snake_case for translation key compliance
                translation_key_name = camel_to_snake(val_name)
                enum_values[edt_decimal] = translation_key_name
                # Extract descriptions.en for UI display (optional field)
                descriptions = item.get("descriptions", {})
                desc_en = descriptions.get("en", "")
                if desc_en:
                    # Replace HTML-like angle brackets with square brackets
                    desc_en = desc_en.replace("<", "[").replace(">", "]")
                    enum_descriptions[translation_key_name] = desc_en

    return MRAProperty(
        epc=epc,
        name_en=name_en,
        name_ja=name_ja,
        get=get_access,
        data_type=data_type,
        mra_format=mra_format,
        mra_unit=mra_unit,
        mra_minimum=mra_minimum,
        mra_maximum=mra_maximum,
        mra_multiple_of=mra_multiple_of,
        enum_values=enum_values,
        enum_descriptions=enum_descriptions,
    )


# ============================================================================
# Entity Building Functions
# ============================================================================


def _make_entity_result(
    platform: str,
    class_code: int,
    epc: int,
    **attrs: Any,
) -> tuple[str, dict[str, Any]]:
    """Create entity result tuple with translation_key."""
    return (
        platform,
        {
            "translation_key": f"class_{class_code:04x}_epc_{epc:02x}",
            **attrs,
        },
    )


def _try_state_entity(
    class_code: int, epc: int, prop: MRAProperty
) -> tuple[str, dict[str, Any]] | None:
    """Try to create binary entity from state type property.

    Only 2-value state properties are supported. Properties with 3+ enum values
    are skipped as they cannot be represented as binary sensors.
    """
    if prop.data_type != "state":
        return None

    name_en = prop.name_en.lower()
    state_keywords = (
        "detection",
        "status",
        "setting",
        "notice",
        "type",
        "interconnect",
    )
    if not any(keyword in name_en for keyword in state_keywords):
        return None

    # Only 2-value states can be represented as binary sensors
    if len(prop.enum_values) > 2:
        return None

    return _make_entity_result("binary", class_code, epc, decoder="binary_on_off")


def determine_entity_type(
    class_code: int,
    epc: int,
    prop: MRAProperty,
    class_name: str,
) -> tuple[str, dict[str, Any]] | None:
    """Determine HA entity type and attributes for a property."""

    # Skip properties without get access
    if not prop.get:
        return None

    # Binary entities - check specific first, then generic
    # State type properties -> binary sensor or select
    if result := _try_state_entity(class_code, epc, prop):
        # Apply device_class override if specified
        device_class = BINARY_DEVICE_CLASS_OVERRIDES.get(
            (class_code, epc)
        ) or BINARY_DEVICE_CLASS_OVERRIDES.get((None, epc))
        if device_class:
            result[1]["device_class"] = device_class
        return result

    return None


def _register_binary_decoder_from_enum(
    enum_vals: dict[str, str], attrs: dict[str, Any]
) -> None:
    """Register binary decoder from enum values.

    Args:
        enum_vals: Enum values dict (e.g., {"65": "true", "66": "false"} in decimal)
        attrs: Entity attributes dict (modified in place)
    """
    enum_items = list(enum_vals.items())
    on_val_str = enum_items[0][0]  # First value is ON (decimal string)
    off_val_str = enum_items[1][0]  # Second value is OFF (decimal string)

    # Convert decimal string to int
    on_val = int(on_val_str)
    off_val = int(off_val_str)

    # Create a unique decoder name using hex representation for readability
    decoder_name = f"binary_on_off_{on_val:02x}_{off_val:02x}"

    # Register this decoder if not already present
    if decoder_name not in DECODERS:
        DECODERS[decoder_name] = {
            "type": "binary",
            "on": on_val,
            "off": off_val,
        }
    attrs["decoder"] = decoder_name


def _build_common_entities(
    class_code: int,
    seen_entity_keys: set[str],
    superclass_props: dict[int, MRAProperty],
) -> list[dict[str, Any]]:
    """Build common entities from superClass 0x0000 for a device class.

    Args:
        class_code: Device class code
        seen_entity_keys: Set of already seen entity keys to avoid duplicates
        superclass_props: MRAProperty objects from superClass for auto-inference

    Returns:
        List of common entity definitions
    """
    common_entities: list[dict[str, Any]] = []

    # Process all common EPCs - exclusion logic is handled by determine_entity_type
    for epc in sorted(COMMON_EPCS):
        prop = superclass_props.get(epc)
        if not prop:
            continue

        entity = _build_entity_from_property(
            class_code, prop, "superClass", seen_entity_keys
        )

        if entity:
            # Override translation_key to use common prefix
            entity["translation_key"] = f"class_common_epc_{epc:02x}"
            common_entities.append(entity)

    return common_entities


def _build_entity_from_property(
    class_code: int,
    prop: MRAProperty,
    class_name: str,
    seen_entity_keys: set[str],
) -> dict[str, Any] | None:
    """Build entity dict from MRA property.

    Args:
        class_code: Device class code
        prop: Parsed MRA property
        class_name: Device class name for warnings
        seen_entity_keys: Set of already seen entity keys (modified in place)

    Returns:
        Entity dict or None if skipped
    """
    entity_info = determine_entity_type(class_code, prop.epc, prop, class_name)
    if not entity_info:
        return None

    platform, attrs = entity_info

    # Deduplicate
    entity_key = f"{platform}_{prop.epc:02x}"
    if entity_key in seen_entity_keys:
        return None
    seen_entity_keys.add(entity_key)

    name_en = prop.name_en
    if not name_en:
        print(
            f"WARNING: Missing English name for class 0x{class_code:04X} EPC 0x{prop.epc:02X}"
        )

    enum_vals = prop.enum_values

    # Determine decoder - prefer explicit definition, fall back to enum_values
    decoder = attrs.get("decoder", "")

    # If no decoder specified but enum_values exist, auto-determine decoder type
    if not decoder and enum_vals:
        if len(enum_vals) == 2:
            # Binary state: on/off (for binary)
            decoder = "binary_on_off"
            if not attrs.get("platform"):
                attrs["platform"] = "binary"
            attrs["decoder"] = decoder
        else:
            # Multiple states (3+) cannot be represented as binary
            # Skip these properties (they would need select platform which is not supported)
            print(
                f"WARNING: Skipping property with {len(enum_vals)} enum values "
                f"for class 0x{class_code:04X} EPC 0x{prop.epc:02X} ({name_en}) - "
                f"multi-value enums are not supported"
            )
            return None

    # Skip entities without decoder - they cannot be created
    if not attrs.get("decoder"):
        print(
            f"WARNING: No decoder for class 0x{class_code:04X} EPC 0x{prop.epc:02X} "
            f"({name_en}), skipping entity"
        )
        return None

    # For binary_on_off decoder with enum values, extract on/off from enum
    if decoder == "binary_on_off" and enum_vals and len(enum_vals) == 2:
        _register_binary_decoder_from_enum(enum_vals, attrs)

    # Build entity with only non-empty fields
    final_platform = attrs.get("platform", platform)
    entity: dict[str, Any] = {
        "platform": final_platform,
        "epc": prop.epc,
        "name_en": name_en,
        "name_ja": prop.name_ja,
        "decoder": attrs.get("decoder", ""),
        "translation_key": attrs.get("translation_key", ""),
    }
    # Add optional fields only if non-empty
    if device_class := attrs.get("device_class"):
        entity["device_class"] = device_class
    if unit := attrs.get("unit"):
        entity["unit"] = unit
    if state_class := attrs.get("state_class"):
        entity["state_class"] = state_class
    # Keep enum_descriptions for all platforms (needed for strings.json generation)
    if prop.enum_descriptions:
        entity["enum_descriptions"] = prop.enum_descriptions

    return entity


# ============================================================================
# Definition Generation Functions
# ============================================================================


def _load_mra_metadata(mra_path: Path) -> tuple[str, dict[str, Any]]:
    """Load MRA metadata and definitions.

    Returns:
        Tuple of (mra_version, mra_definitions dict)
    """
    # Load metadata for version info
    with (mra_path / "metaData.json").open(encoding="utf-8") as f:
        metadata = json.load(f)
    mra_version = metadata["metaData"]["dataVersion"]

    # Load definitions for $ref resolution
    with (mra_path / "definitions" / "definitions.json").open(encoding="utf-8") as f:
        defs_data = json.load(f)
    mra_definitions = defs_data["definitions"]

    return mra_version, mra_definitions


def _load_superclass_props(
    mra_path: Path, mra_definitions: dict[str, Any]
) -> dict[int, MRAProperty]:
    """Load superClass/0x0000.json for common property definitions.

    Returns:
        Dictionary mapping EPC to MRAProperty
    """
    with (mra_path / "superClass" / "0x0000.json").open(encoding="utf-8") as f:
        superclass = json.load(f)
    return {
        (prop := parse_mra_property(prop_data, mra_definitions)).epc: prop
        for prop_data in superclass["elProperties"]
    }


def generate_definitions(mra_path: Path) -> dict[str, Any]:
    """Generate definitions from MRA data."""
    devices_path = mra_path / "devices"
    if not devices_path.exists():
        print(f"Error: devices directory not found at {devices_path}")
        return {}

    mra_version, mra_definitions = _load_mra_metadata(mra_path)
    superclass_props = _load_superclass_props(mra_path, mra_definitions)

    devices: dict[int, dict[str, Any]] = {}

    for device_file in sorted(devices_path.glob("0x*.json")):
        # Filename format is guaranteed by glob pattern "0x*.json"
        class_code = int(device_file.stem, 16)

        with device_file.open(encoding="utf-8") as f:
            data = json.load(f)

        class_name_data = data["className"]
        class_name = class_name_data["en"] or class_name_data["ja"]

        # Parse properties
        entities: list[dict[str, Any]] = []
        seen_entity_keys: set[str] = set()

        for prop_data in data["elProperties"]:
            prop = parse_mra_property(prop_data, mra_definitions)

            # Skip common EPCs - they will be processed by _build_common_entities
            # to ensure consistent translation_key (class_common_epc_xx)
            if prop.epc in COMMON_EPCS:
                continue

            entity = _build_entity_from_property(
                class_code, prop, class_name, seen_entity_keys
            )
            if entity:
                entities.append(entity)

        # Expand common properties (power sensors, operation status) into this class
        common_epcs_to_add = _build_common_entities(
            class_code, seen_entity_keys, superclass_props
        )

        # Insert common properties at the beginning for consistent ordering
        entities = common_epcs_to_add + entities

        if entities:
            devices[class_code] = {
                "name_en": class_name_data["en"],
                "name_ja": class_name_data["ja"],
                "entities": entities,
            }

    return {
        "version": "1.0.0",
        "mra_version": mra_version,
        "devices": devices,
        "decoders": DECODERS,
    }


# ============================================================================
# Strings Generation
# ============================================================================


def generate_strings(definitions: dict[str, Any]) -> dict[str, Any]:
    """Generate entity strings for strings.json from definitions.

    Returns:
        Dictionary with config, options, and entity sections for strings.json.
    """
    entity_strings: dict[str, dict[str, dict[str, Any]]] = {}

    def _add_entity_string(
        platform: str,
        translation_key: str,
        name_en: str,
        enum_descriptions: dict[str, str] | None,
        is_binary: bool = False,
    ) -> None:
        """Add entity string with optional state translations."""
        if platform not in entity_strings:
            entity_strings[platform] = {}
        entry: dict[str, Any] = {"name": name_en or translation_key}
        # Add state translations if enum_descriptions exist
        if enum_descriptions:
            if is_binary and len(enum_descriptions) == 2:
                # For binary sensors, convert enum_descriptions to off/on keys
                # MRA order: first value = ON (detected), second value = OFF (not_detected)
                desc_items = list(enum_descriptions.items())
                entry["state"] = {
                    "on": desc_items[0][1],  # First enum = ON state
                    "off": desc_items[1][1],  # Second enum = OFF state
                }
            else:
                entry["state"] = enum_descriptions
        entity_strings[platform][translation_key] = entry

    # Process device-specific entities (all entities are now per-device)
    for device in definitions.get("devices", {}).values():
        for entity in device.get("entities", []):
            platform = entity.get("platform")
            translation_key = entity.get("translation_key")
            name_en = entity.get("name_en", "")
            enum_descriptions = entity.get("enum_descriptions")

            if not platform or not translation_key:
                continue

            # For binary, add to switch only
            if platform == "binary":
                _add_entity_string(
                    "switch",
                    translation_key,
                    name_en,
                    enum_descriptions,
                    is_binary=True,
                )
            else:
                _add_entity_string(
                    platform, translation_key, name_en, enum_descriptions
                )

    # Load static sections from external file
    with STRINGS_STATIC_FILE.open(encoding="utf-8") as f:
        static_strings = json.load(f)

    return {
        "config": static_strings["config"],
        "issues": static_strings["issues"],
        "options": static_strings["options"],
        "entity": entity_strings,
    }


# ============================================================================
# Main Entry Point
# ============================================================================


def main() -> None:
    """Main entry point."""
    print("Downloading/updating MRA data...")
    fetcher = MRAFetcher()

    try:
        mra_path = fetcher.ensure_mra()
        print(f"MRA data available at: {mra_path}")
    except Exception as ex:  # noqa: BLE001
        print(f"Failed to fetch MRA: {ex}")
        # Try to use cached data
        if fetcher.is_cached:
            mra_path = fetcher.cache_dir
            print(f"Using cached MRA data at: {mra_path}")
        else:
            print("No cached MRA data available. Exiting.")
            return

    print("Generating definitions...")
    definitions = generate_definitions(mra_path)

    # Generate entity strings (must be done before stripping enum_descriptions)
    strings_data = generate_strings(definitions)

    # Strip enum_descriptions from definitions before writing to definitions.json
    # (enum_descriptions is only used for strings.json generation)
    for device in definitions.get("devices", {}).values():
        for entity in device.get("entities", []):
            entity.pop("enum_descriptions", None)

    # Write definitions.json
    definitions_path = ECHONET_LITE_DIR / "definitions.json"
    with definitions_path.open("w", encoding="utf-8") as f:
        json.dump(definitions, f, indent=2, ensure_ascii=False)
    print(f"Generated: {definitions_path}")

    # Write strings.json (fully generated, no merge needed)
    strings_path = ECHONET_LITE_DIR / "strings.json"
    with strings_path.open("w", encoding="utf-8") as f:
        json.dump(strings_data, f, indent=2, ensure_ascii=False)
    print(f"Generated: {strings_path}")

    # Print summary
    device_count = len(definitions.get("devices", {}))
    entity_count = sum(
        len(d.get("entities", [])) for d in definitions.get("devices", {}).values()
    )
    print("\nSummary:")
    print(f"  MRA version: {definitions.get('mra_version', 'unknown')}")
    print(f"  Devices: {device_count}")
    print(f"  Entities: {entity_count}")
    print("\nRun 'pre-commit run --files <files>' to format generated files.")


if __name__ == "__main__":
    main()
