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

Output files:
- homeassistant/components/echonet_lite/strings.json

Note: Translations (translations/*.json) are managed by Lokalise and should not
be committed. Only strings.json (English base) is version controlled.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyhems import load_definitions_registry
from pyhems.definitions import DefinitionsRegistry, EntityDefinition

# ============================================================================
# Constants
# ============================================================================

ECHONET_LITE_DIR = Path(__file__).parent.parent
GENERATOR_DIR = Path(__file__).parent
STRINGS_STATIC_FILE = GENERATOR_DIR / "strings_static.json"


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
        platform: Entity platform (switch)
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
) -> None:
    """Process a single entity definition.

    Args:
        entity_strings: Dictionary to add entity strings to.
        entity: EntityDefinition dataclass from pyhems.
    """
    # Only process binary entities (2 enum values) for switch platform
    if entity.enum_values and len(entity.enum_values) == 2:
        state = {
            "on": _escape_html_brackets(entity.enum_values[0].name_en),
            "off": _escape_html_brackets(entity.enum_values[1].name_en),
        }
        _add_entity_string(entity_strings, "switch", entity, state)
    # Skip entities with >2 enum values (select platform removed)
    # Skip numeric entities (sensor platform removed)


def generate_strings(registry: DefinitionsRegistry) -> dict[str, Any]:
    """Generate entity strings for strings.json from DefinitionsRegistry.

    Args:
        registry: DefinitionsRegistry loaded from pyhems.

    Returns:
        Dictionary with config, options, issues, and entity sections.
    """
    entity_strings: dict[str, dict[str, dict[str, Any]]] = {}

    # Process all entities from DefinitionsRegistry
    # DefinitionsRegistry already has common entities merged into each device
    for entity_defs in registry.entities.values():
        for entity in entity_defs:
            _process_entity(entity_strings, entity)

    # Load static sections and merge generated entity strings
    with STRINGS_STATIC_FILE.open(encoding="utf-8") as f:
        result = json.load(f)

    # Merge generated entity strings into static entity section
    for platform, platform_entities in entity_strings.items():
        result["entity"].setdefault(platform, {}).update(platform_entities)

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

    # Print summary
    print("\nSummary:")
    print(f"  MRA version: {registry.mra_version}")
    print(f"  Device classes: {len(all_class_codes)}")
    print(f"  Entities (total across platforms): {entity_count}")
    print("\nRun 'pre-commit run --files <files>' to format generated files.")


if __name__ == "__main__":
    main()
