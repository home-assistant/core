# ruff: noqa: T201
"""Generate strings.json for the ECHONET Lite integration.

This script generates strings.json from pyhems definitions for entity
translations. It does NOT generate definitions.json - that is provided
by the pyhems library.

Run with: python -m homeassistant.components.echonet_lite.generator.generate_strings

Requires pyhems to be installed in the environment:
- Development: uv pip install -e /workspaces/pyhems
- Released: uv pip install pyhems

Input files:
- pyhems definitions.json (source of entity definitions with translation_key)
- generator/strings_static.json (static strings for config, options, issues)
- homeassistant/strings.json (common state translations for key references)

Output files:
- homeassistant/components/echonet_lite/strings.json

Note: Translations (translations/*.json) are managed by Lokalise and should not
be committed. Only strings.json (English base) is version controlled.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from pyhems import DefinitionsRegistry, EntityDefinition, load_definitions_registry

from ..entity import can_process_enum_values, infer_platform

# ============================================================================
# Constants
# ============================================================================

ECHONET_LITE_DIR = Path(__file__).parent.parent
GENERATOR_DIR = Path(__file__).parent
REPO_ROOT = ECHONET_LITE_DIR.parent.parent.parent
STRINGS_STATIC_FILE = GENERATOR_DIR / "strings_static.json"
HA_STRINGS_FILE = ECHONET_LITE_DIR.parent.parent / "strings.json"

# Reference prefix for integration-local common strings
_LOCAL_COMMON_REF_PREFIX = "[%key:component::echonet_lite::common::"

# Minimum number of occurrences for a value to be deduplicated into common
_DEDUP_THRESHOLD = 2


# ============================================================================
# Text-to-Key Conversion
# ============================================================================


def _text_to_common_key(text: str) -> str:
    """Convert English display text to a snake_case key for common section.

    The key must match HA's translation key regex: [a-z0-9-_]+

    Args:
        text: English display text (e.g., "Level 1", "Not detected").

    Returns:
        snake_case key (e.g., "level_1", "not_detected").
    """
    key = text.lower()
    # Remove characters not allowed in keys (keep alphanumeric, space, hyphen)
    key = re.sub(r"[^a-z0-9 \-]", "", key)
    # Replace spaces and hyphens with underscores
    key = re.sub(r"[\s\-]+", "_", key)
    # Collapse consecutive underscores and strip leading/trailing
    return re.sub(r"_+", "_", key).strip("_")


# ============================================================================
# Deduplication
# ============================================================================


def _is_key_reference(value: str) -> bool:
    """Check if a string value is already a key reference."""
    return value.startswith("[%key:")


def _collect_value_counts(
    entity_strings: dict[str, dict[str, dict[str, Any]]],
) -> Counter[str]:
    """Count occurrences of each non-reference string value across all entities.

    Counts both entity names and state values. Values that are already
    key references ([%key:...%]) are excluded.

    Args:
        entity_strings: Generated entity strings dict.

    Returns:
        Counter mapping text values to their occurrence count.
    """
    counts: Counter[str] = Counter()
    for platform_entities in entity_strings.values():
        for entity_entry in platform_entities.values():
            # Count entity name
            name = entity_entry.get("name", "")
            if name and not _is_key_reference(name):
                counts[name] += 1
            # Count state values
            if state := entity_entry.get("state"):
                for state_value in state.values():
                    if state_value and not _is_key_reference(state_value):
                        counts[state_value] += 1
    return counts


def _build_common_section(
    value_counts: Counter[str],
) -> dict[str, str]:
    """Build a common section from values that appear multiple times.

    Assigns a snake_case key to each duplicated value, resolving key
    collisions with numeric suffixes (_2, _3, ...).

    Args:
        value_counts: Counter of non-reference string values.

    Returns:
        Dictionary mapping common keys to text values, sorted by key.
    """
    used_keys: dict[str, str] = {}  # key -> text
    text_to_key: dict[str, str] = {}  # text -> key

    # Process values sorted by text for deterministic output
    for text, count in sorted(value_counts.items()):
        if count < _DEDUP_THRESHOLD:
            continue
        base_key = _text_to_common_key(text)
        if not base_key:
            continue

        # Resolve key collisions
        candidate = base_key
        suffix = 2
        while candidate in used_keys and used_keys[candidate] != text:
            candidate = f"{base_key}_{suffix}"
            suffix += 1

        used_keys[candidate] = text
        text_to_key[candidate] = text

    # Return sorted by key
    return dict(sorted(text_to_key.items()))


def _build_text_to_ref(common_section: dict[str, str]) -> dict[str, str]:
    """Build a reverse lookup from text to key reference string.

    Args:
        common_section: The common section (key -> text).

    Returns:
        Dictionary mapping text to reference string.
    """
    return {
        text: f"{_LOCAL_COMMON_REF_PREFIX}{key}%]"
        for key, text in common_section.items()
    }


def _replace_with_references(
    entity_strings: dict[str, dict[str, dict[str, Any]]],
    text_to_ref: dict[str, str],
) -> int:
    """Replace duplicated values with common section references in-place.

    Only replaces values that are not already key references.

    Args:
        entity_strings: Generated entity strings dict (mutated in-place).
        text_to_ref: Mapping from text to reference string.

    Returns:
        Number of replacements made.
    """
    replacements = 0
    for platform_entities in entity_strings.values():
        for entity_entry in platform_entities.values():
            # Replace entity name
            name = entity_entry.get("name", "")
            if name and not _is_key_reference(name) and name in text_to_ref:
                entity_entry["name"] = text_to_ref[name]
                replacements += 1
            # Replace state values
            if state := entity_entry.get("state"):
                for state_key, state_value in state.items():
                    if (
                        state_value
                        and not _is_key_reference(state_value)
                        and state_value in text_to_ref
                    ):
                        state[state_key] = text_to_ref[state_value]
                        replacements += 1
    return replacements


# ============================================================================
# Common State References
# ============================================================================


def _load_common_states() -> dict[str, str]:
    """Load common::state translations from homeassistant/strings.json.

    Returns:
        Dictionary mapping state keys to English text
        (e.g., {"auto": "Auto", "on": "On"}).
    """
    with HA_STRINGS_FILE.open(encoding="utf-8") as f:
        ha_strings = json.load(f)
    return ha_strings.get("common", {}).get("state", {})


def _build_reverse_lookup(common_states: dict[str, str]) -> dict[str, str]:
    """Build a reverse lookup from lowercase English text to state key.

    Maps lowercase display text to the first matching common::state key.
    Used for name_en-based matching.

    Args:
        common_states: Dictionary of common::state key-value pairs.

    Returns:
        Dictionary mapping lowercase text to key
        (e.g., {"auto": "auto", "on": "on", "open": "open"}).
    """
    return {text.lower(): key for key, text in common_states.items()}


def _resolve_by_name(
    text: str,
    reverse_lookup: dict[str, str],
) -> str:
    """Resolve state value for switch: match by name_en only.

    Switch keys are always "on"/"off" and carry no semantic meaning.
    Only the display text (name_en) is used for matching.

    Args:
        text: English display text (e.g., "Open", "Closed", "YES").
        reverse_lookup: Reverse lookup from lowercase text to state key.

    Returns:
        Key reference string or original text.
    """
    cs_key = reverse_lookup.get(text.lower())
    if cs_key is not None:
        return f"[%key:common::state::{cs_key}%]"
    return text


# ============================================================================
# Strings Generation
# ============================================================================


def _escape_html_brackets(text: str) -> str:
    """Escape angle brackets to square brackets.

    HA translation validation rejects strings containing < or > as HTML.
    MRA data uses angle brackets for categorization (e.g., "<Drying course>").
    """
    return text.replace("<", "[").replace(">", "]")


def _add_entity_string(
    entity_strings: dict[str, dict[str, dict[str, Any]]],
    platform: str,
    entity: EntityDefinition,
    state: dict[str, str] | None,
) -> None:
    """Add entity string with optional state translations.

    Args:
        entity_strings: Dictionary to add entity strings to.
        platform: Entity platform (binary_sensor, switch, select, sensor)
        entity: EntityDefinition dataclass from pyhems
        state: State translations (on/off for binary, key/name for select)
    """
    entry: dict[str, Any] = {"name": _escape_html_brackets(entity.name_en)}
    if state:
        entry["state"] = state
    entity_strings.setdefault(platform, {})[entity.id] = entry


def _process_entity(
    entity_strings: dict[str, dict[str, dict[str, Any]]],
    entity: EntityDefinition,
    reverse_lookup: dict[str, str],
) -> None:
    """Process a single entity definition.

    Uses infer_platform() to determine if the entity is a switch.
    Only switch entities are processed; all others are skipped.

    State matching uses name_en only for switch (keys are always on/off).

    Args:
        entity_strings: Dictionary to add entity strings to.
        entity: EntityDefinition dataclass from pyhems.
        reverse_lookup: Reverse lookup from lowercase text to state key.
    """
    # Skip entities with non-processable enum values
    if not can_process_enum_values(entity):
        return

    platform = infer_platform(entity)

    if platform == "switch":
        # 2-enum entity: match by name_en only
        on_text = _escape_html_brackets(entity.enum_values[0].name_en)
        off_text = _escape_html_brackets(entity.enum_values[1].name_en)
        state = {
            "on": _resolve_by_name(on_text, reverse_lookup),
            "off": _resolve_by_name(off_text, reverse_lookup),
        }
        _add_entity_string(entity_strings, "switch", entity, state)


def generate_strings(registry: DefinitionsRegistry) -> dict[str, Any]:
    """Generate entity strings for strings.json from DefinitionsRegistry.

    Uses a multi-pass approach:
    1. Generate all entity strings (names + state values)
    2. Collect duplicate non-reference values (threshold >= 2 occurrences)
    3. Build a common section with snake_case keys for duplicated values
    4. Replace duplicated values with [%key:component::echonet_lite::common::KEY%]

    Static entries from strings_static.json take priority over generated ones.
    This allows manual overrides of auto-generated translations.

    Args:
        registry: DefinitionsRegistry loaded from pyhems.

    Returns:
        Dictionary with common, config, options, issues, and entity sections.
    """
    common_states = _load_common_states()
    reverse_lookup = _build_reverse_lookup(common_states)
    entity_strings: dict[str, dict[str, dict[str, Any]]] = {}

    # Pass 1: Process all entities from DefinitionsRegistry
    # DefinitionsRegistry already has common entities merged into each device
    for entity_defs in registry.entities.values():
        for entity in entity_defs:
            _process_entity(
                entity_strings,
                entity,
                reverse_lookup,
            )

    # Pass 2: Detect duplicates and build common section
    value_counts = _collect_value_counts(entity_strings)
    common_section = _build_common_section(value_counts)

    # Pass 3: Replace duplicated values with common references
    text_to_ref = _build_text_to_ref(common_section)
    _replace_with_references(entity_strings, text_to_ref)

    # Load static sections and merge generated entity strings
    with STRINGS_STATIC_FILE.open(encoding="utf-8") as f:
        result = json.load(f)

    # Merge common section (static common entries take priority)
    if common_section:
        static_common = result.setdefault("common", {})
        for key, value in common_section.items():
            static_common.setdefault(key, value)

    # Merge generated entity strings into static entity section
    # Static entries take priority over generated ones (setdefault skips
    # entities already defined in strings_static.json)
    for platform, platform_entities in sorted(entity_strings.items()):
        static_platform = result["entity"].setdefault(platform, {})
        for entity_key, entity_value in sorted(platform_entities.items()):
            static_platform.setdefault(entity_key, entity_value)

    # Ensure "common" is the first key in the output for readability
    # (json.dump preserves dict insertion order)
    if "common" in result:
        common = result.pop("common")
        result = {"common": common, **result}

    return result


# ============================================================================
# Main Entry Point
# ============================================================================


def main() -> None:
    """Main entry point."""
    print("Loading pyhems DefinitionsRegistry...")
    registry = load_definitions_registry()
    print(f"  MRA version: {registry.mra_version}")

    # Count unique class codes and entities
    all_class_codes = set(registry.entities.keys())
    entity_count = sum(len(entities) for entities in registry.entities.values())
    print(f"  Device classes: {len(all_class_codes)}")

    print("Generating strings.json...")
    strings_data = generate_strings(registry)

    # Write strings.json
    strings_path = ECHONET_LITE_DIR / "strings.json"
    with strings_path.open("w", encoding="utf-8") as f:
        json.dump(strings_data, f, indent=2, ensure_ascii=False)
    print(f"Generated: {strings_path}")

    print("Formatting strings.json with prettier...")
    subprocess.run(
        [
            "prek",
            "run",
            "prettier",
            "--files",
            str(strings_path),
        ],
        check=False,
        cwd=REPO_ROOT,
    )

    # Print summary
    common_count = len(strings_data.get("common", {}))
    print("\nSummary:")
    print(f"  MRA version: {registry.mra_version}")
    print(f"  Device classes: {len(all_class_codes)}")
    print(f"  Entities (total across platforms): {entity_count}")
    print(f"  Common strings: {common_count}")


if __name__ == "__main__":
    main()
