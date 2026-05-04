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


def _canonicalize_common_text(text: str) -> str:
    """Canonicalize text for dedup grouping.

    Canonicalization rules intentionally only normalize:
    - case differences
    - separator differences between spaces and hyphens

    This allows values like "Reservation OFF" and "Reservation off", or
    "System interconnected type" and "System-interconnected type", to be
    treated as the same value bucket before key assignment.
    """
    return re.sub(r"\s+", " ", text.lower().replace("-", " ")).strip()


# ============================================================================
# Deduplication
# ============================================================================


def _is_key_reference(value: str) -> bool:
    """Check if a string value is already a key reference."""
    return value.startswith("[%key:")


def _count_state_values(state: dict[str, str], counts: Counter[str]) -> None:
    """Count non-reference string values in a state dict."""
    for state_value in state.values():
        if state_value and not _is_key_reference(state_value):
            counts[state_value] += 1


def _collect_value_counts(
    entity_strings: dict[str, dict[str, dict[str, Any]]],
) -> Counter[str]:
    """Count occurrences of each non-reference string value across all entities.

    Counts entity names, state values, and state_attributes state values.
    Values that are already key references ([%key:...%]) are excluded.

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
                _count_state_values(state, counts)
            # Count state_attributes state values
            if state_attrs := entity_entry.get("state_attributes"):
                for attr_entry in state_attrs.values():
                    if attr_state := attr_entry.get("state"):
                        _count_state_values(attr_state, counts)
    return counts


def _build_common_section(
    value_counts: Counter[str],
) -> dict[str, str]:
    """Build a common section from values that appear multiple times.

    Values are first grouped by canonical text to absorb case-only and
    hyphen/space-only variants into a single bucket.

    A single representative text is selected per canonical bucket using:
    1. highest occurrence count
    2. lexicographical order of text as deterministic tie-breaker

    If distinct canonical buckets still map to the same common key, this is
    treated as a real key-generation ambiguity and raises ValueError.

    Args:
        value_counts: Counter of non-reference string values.

    Returns:
        Dictionary mapping common keys to text values, sorted by key.
    """
    canonical_buckets: dict[str, list[tuple[str, int]]] = {}
    for text, count in value_counts.items():
        canonical = _canonicalize_common_text(text)
        if not canonical:
            continue
        canonical_buckets.setdefault(canonical, []).append((text, count))

    used_keys: dict[str, tuple[str, str]] = {}
    text_to_key: dict[str, str] = {}

    # Process canonical buckets sorted by canonical text for deterministic output
    for canonical, items in sorted(canonical_buckets.items()):
        total_count = sum(count for _, count in items)
        if total_count < _DEDUP_THRESHOLD:
            continue

        # Representative text: highest count, then lexical order for stability
        representative_text = sorted(items, key=lambda item: (-item[1], item[0]))[0][0]
        key = _text_to_common_key(canonical)
        if not key:
            continue

        if key in used_keys and used_keys[key][0] != canonical:
            existing_canonical, existing_text = used_keys[key]
            raise ValueError(
                "Common key collision after canonical grouping: "
                f"key='{key}', "
                f"canonical_a='{existing_canonical}' (text='{existing_text}'), "
                f"canonical_b='{canonical}' (text='{representative_text}')"
            )

        used_keys[key] = (canonical, representative_text)
        text_to_key[key] = representative_text

    # Return sorted by key
    return dict(sorted(text_to_key.items()))


def _build_text_to_ref(common_section: dict[str, str]) -> dict[str, str]:
    """Build a reverse lookup from canonical text to key reference string.

    Args:
        common_section: The common section (key -> text).

    Returns:
        Dictionary mapping canonical text to reference string.
    """
    return {
        _canonicalize_common_text(text): f"{_LOCAL_COMMON_REF_PREFIX}{key}%]"
        for key, text in common_section.items()
    }


def _replace_state_values(state: dict[str, str], text_to_ref: dict[str, str]) -> int:
    """Replace non-reference values with common references in a state dict."""
    replacements = 0
    for state_key, state_value in state.items():
        canonical_value = _canonicalize_common_text(state_value) if state_value else ""
        if (
            state_value
            and not _is_key_reference(state_value)
            and canonical_value in text_to_ref
        ):
            state[state_key] = text_to_ref[canonical_value]
            replacements += 1
    return replacements


def _replace_with_references(
    entity_strings: dict[str, dict[str, dict[str, Any]]],
    text_to_ref: dict[str, str],
) -> int:
    """Replace duplicated values with common section references in-place.

    Only replaces values that are not already key references.
    Handles both top-level state and nested state_attributes state.

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
            canonical_name = _canonicalize_common_text(name) if name else ""
            if name and not _is_key_reference(name) and canonical_name in text_to_ref:
                entity_entry["name"] = text_to_ref[canonical_name]
                replacements += 1
            # Replace state values
            if state := entity_entry.get("state"):
                replacements += _replace_state_values(state, text_to_ref)
            # Replace state_attributes state values
            if state_attrs := entity_entry.get("state_attributes"):
                for attr_entry in state_attrs.values():
                    if attr_state := attr_entry.get("state"):
                        replacements += _replace_state_values(attr_state, text_to_ref)
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
        ha_strings: dict[str, Any] = json.load(f)
    result: dict[str, str] = ha_strings.get("common", {}).get("state", {})
    return result


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
        platform: Entity platform (only "switch" is used here)
        entity: EntityDefinition dataclass from pyhems
        state: State translations (on/off for switch)
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

    Static entity entries from strings_static.json are merged into the
    generated set before deduplication, so static plain-text values also
    participate in common section extraction. Static entries take priority
    over generated ones for the same entity key.

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

    # Load static file early to merge entity section before deduplication
    with STRINGS_STATIC_FILE.open(encoding="utf-8") as f:
        static_data = json.load(f)

    # Merge static entity entries into entity_strings (static takes priority)
    # This ensures static plain-text values participate in deduplication
    for platform, platform_entities in static_data.get("entity", {}).items():
        gen_platform = entity_strings.setdefault(platform, {})
        for entity_key, entity_value in platform_entities.items():
            gen_platform[entity_key] = entity_value

    # Pass 2: Detect duplicates and build common section
    value_counts = _collect_value_counts(entity_strings)
    common_section = _build_common_section(value_counts)

    # Pass 3: Replace duplicated values with common references
    text_to_ref = _build_text_to_ref(common_section)
    _replace_with_references(entity_strings, text_to_ref)

    # Build result from static non-entity sections
    result: dict[str, Any] = {k: v for k, v in static_data.items() if k != "entity"}

    # Merge common section (static common entries take priority)
    if common_section:
        result_common = result.setdefault("common", {})
        for key, value in common_section.items():
            result_common.setdefault(key, value)

    # Set entity section from fully processed entity_strings
    result["entity"] = {}
    for platform, platform_entities in sorted(entity_strings.items()):
        result["entity"][platform] = dict(sorted(platform_entities.items()))

    # Ensure "common" is the first key in the output for readability
    # (json.dump preserves dict insertion order)
    if "common" in result:
        common = result.pop("common")
        result = {"common": common, **result}

    return result


# ============================================================================
# Main Entry Point
# ============================================================================


def main() -> None:  # pragma: no cover - CLI entry point exercised by smoke test only
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
        json.dump(strings_data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(f"Generated: {strings_path}")

    # Print summary
    common_count = len(strings_data.get("common", {}))
    print("\nSummary:")
    print(f"  MRA version: {registry.mra_version}")
    print(f"  Device classes: {len(all_class_codes)}")
    print(f"  Entities (total across platforms): {entity_count}")
    print(f"  Common strings: {common_count}")


if __name__ == "__main__":  # pragma: no cover
    main()
