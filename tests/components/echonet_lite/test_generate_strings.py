"""Tests for generate_strings.py - HA-specific strings.json generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyhems import load_definitions_registry
from pyhems.definitions import DefinitionsRegistry, EntityDefinition, EnumValue
import pytest

from homeassistant.components.echonet_lite.generator.generate_strings import (
    _add_entity_string,
    _escape_html_brackets,
    _process_entity,
    generate_strings,
)
from homeassistant.components.echonet_lite.switch import _create_switch_description

# Path to HA strings.json
STRINGS_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "homeassistant"
    / "components"
    / "echonet_lite"
    / "strings.json"
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def registry() -> DefinitionsRegistry:
    """Load pyhems DefinitionsRegistry."""
    return load_definitions_registry()


@pytest.fixture
def strings() -> dict[str, Any]:
    """Load strings.json."""
    with open(STRINGS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# Tests for helper functions
# ============================================================================


class TestEscapeHtmlBrackets:
    """Test _escape_html_brackets helper function."""

    def test_escape_angle_brackets(self) -> None:
        """Test that angle brackets are escaped to square brackets."""
        assert _escape_html_brackets("<test>") == "[test]"
        assert _escape_html_brackets("<Drying course>") == "[Drying course]"

    def test_no_brackets(self) -> None:
        """Test that text without brackets is unchanged."""
        assert _escape_html_brackets("Normal text") == "Normal text"

    def test_mixed_content(self) -> None:
        """Test text with mixed content."""
        assert _escape_html_brackets("Value <min> to <max>") == "Value [min] to [max]"


class TestAddEntityString:
    """Test _add_entity_string helper function."""

    def test_add_entity_without_state(self) -> None:
        """Test adding entity string without state translations."""
        entity_strings: dict[str, dict[str, dict[str, Any]]] = {}
        entity = EntityDefinition(
            id="test_entity",
            epc=0x80,
            name_en="Test Entity",
            name_ja="テストエンティティ",
            enum_values=(),
        )
        _add_entity_string(entity_strings, "switch", entity, None)

        assert "switch" in entity_strings
        assert "test_entity" in entity_strings["switch"]
        assert entity_strings["switch"]["test_entity"]["name"] == "Test Entity"
        assert "state" not in entity_strings["switch"]["test_entity"]

    def test_add_entity_with_state(self) -> None:
        """Test adding entity string with state translations."""
        entity_strings: dict[str, dict[str, dict[str, Any]]] = {}
        entity = EntityDefinition(
            id="test_switch",
            epc=0x80,
            name_en="Test Switch",
            name_ja="テストスイッチ",
            enum_values=(
                EnumValue(edt=0x30, key="true", name_en="ON", name_ja="オン"),
                EnumValue(edt=0x31, key="false", name_en="OFF", name_ja="オフ"),
            ),
        )
        state = {"on": "ON", "off": "OFF"}
        _add_entity_string(entity_strings, "switch", entity, state)

        assert "switch" in entity_strings
        assert "test_switch" in entity_strings["switch"]
        assert entity_strings["switch"]["test_switch"]["name"] == "Test Switch"
        assert entity_strings["switch"]["test_switch"]["state"] == {
            "on": "ON",
            "off": "OFF",
        }


class TestProcessEntity:
    """Test _process_entity helper function."""

    def test_process_binary_entity(self) -> None:
        """Test processing binary entity creates switch strings."""
        entity_strings: dict[str, dict[str, dict[str, Any]]] = {}
        entity = EntityDefinition(
            id="operation_status",
            epc=0x80,
            name_en="Operation status",
            name_ja="動作状態",
            enum_values=(
                EnumValue(edt=0x30, key="true", name_en="ON", name_ja="オン"),
                EnumValue(edt=0x31, key="false", name_en="OFF", name_ja="オフ"),
            ),
        )
        _process_entity(entity_strings, entity)

        # Binary entities create switch strings only
        assert "switch" in entity_strings
        assert "operation_status" in entity_strings["switch"]
        assert entity_strings["switch"]["operation_status"]["state"]["on"] == "ON"
        assert entity_strings["switch"]["operation_status"]["state"]["off"] == "OFF"

    def test_process_entity_with_numeric_skipped(self) -> None:
        """Test that numeric entities (no enum_values) are skipped."""
        entity_strings: dict[str, dict[str, dict[str, Any]]] = {}
        entity = EntityDefinition(
            id="temperature",
            epc=0xE0,
            name_en="Temperature",
            name_ja="温度",
            format="int16",
            unit="Celsius",
            multiple_of=0.1,
            enum_values=(),
        )
        _process_entity(entity_strings, entity)

        # Numeric entities are skipped (sensor platform removed)
        assert entity_strings == {}

    def test_process_entity_with_many_enums_skipped(self) -> None:
        """Test that entities with >2 enum_values are skipped."""
        entity_strings: dict[str, dict[str, dict[str, Any]]] = {}
        entity = EntityDefinition(
            id="operation_mode",
            epc=0xB0,
            name_en="Operation mode",
            name_ja="動作モード",
            enum_values=(
                EnumValue(
                    edt=0x41, key="automatic", name_en="Automatic", name_ja="自動"
                ),
                EnumValue(edt=0x42, key="cooling", name_en="Cooling", name_ja="冷房"),
                EnumValue(edt=0x43, key="heating", name_en="Heating", name_ja="暖房"),
            ),
        )
        _process_entity(entity_strings, entity)

        # Entities with >2 enum values are skipped (select platform removed)
        assert entity_strings == {}


# ============================================================================
# Tests for generate_strings function
# ============================================================================


class TestGenerateStrings:
    """Test generate_strings function."""

    def test_generate_strings_has_required_sections(
        self, registry: DefinitionsRegistry
    ) -> None:
        """Test that generated strings has required sections."""
        result = generate_strings(registry)

        assert "config" in result
        assert "issues" in result
        assert "options" in result
        assert "entity" in result

    def test_generate_strings_creates_switch_entities(
        self, registry: DefinitionsRegistry
    ) -> None:
        """Test that switch entities are created from binary definitions."""
        result = generate_strings(registry)

        # Should have switch section with entities
        assert "switch" in result.get("entity", {})
        switch_entities = result["entity"]["switch"]
        assert len(switch_entities) > 0

    def test_generate_strings_preserves_static_sections(
        self, registry: DefinitionsRegistry
    ) -> None:
        """Test that static sections from strings_static.json are preserved."""
        result = generate_strings(registry)

        # Check config section has expected structure from static file
        assert "step" in result.get("config", {})
        assert "user" in result["config"]["step"]


# ============================================================================
# Tests for strings.json validation
# ============================================================================


class TestStringsJsonValidation:
    """Test that strings.json has correct structure."""

    def test_strings_has_required_sections(self, strings: dict[str, Any]) -> None:
        """Test that strings.json has required sections."""
        assert "config" in strings
        assert "issues" in strings
        assert "options" in strings
        assert "entity" in strings

    def test_strings_entity_has_switch_section(self, strings: dict[str, Any]) -> None:
        """Test that entity section has switch platform."""
        entity_section = strings.get("entity", {})
        assert "switch" in entity_section, "Should have switch in entity strings"

    def test_strings_matches_generated_output(
        self, registry: DefinitionsRegistry, strings: dict[str, Any]
    ) -> None:
        """Test that strings.json matches what generate_strings would produce."""
        generated = generate_strings(registry)

        # Compare entity sections
        for platform in ("switch",):
            generated_entities = generated.get("entity", {}).get(platform, {})
            current_entities = strings.get("entity", {}).get(platform, {})

            assert generated_entities == current_entities, (
                f"strings.json {platform} section does not match generated output. "
                "Run 'python -m homeassistant.components.echonet_lite.generator.generate_strings' "
                "to regenerate."
            )


# ============================================================================
# Tests for definitions-strings consistency
# ============================================================================


class TestDefinitionsStringsConsistency:
    """Test that all definitions have corresponding strings entries."""

    def test_all_binary_entities_have_switch_strings(
        self, registry: DefinitionsRegistry, strings: dict[str, Any]
    ) -> None:
        """Test that all binary entities have corresponding switch strings."""
        switch_strings = strings.get("entity", {}).get("switch", {})

        for class_code, entities in registry.entities.items():
            for entity in entities:
                # Binary entities have exactly 2 enum_values
                if len(entity.enum_values) != 2:
                    continue

                assert entity.id in switch_strings, (
                    f"Binary entity for class {class_code} EPC {entity.epc} "
                    f"id '{entity.id}' missing switch string entry"
                )


# ============================================================================
# Tests for entity description creation
# ============================================================================


class TestSwitchDescriptionCreation:
    """Test that switch entity descriptions can be created from definitions."""

    def test_all_binary_entities_create_valid_descriptions(
        self, registry: DefinitionsRegistry
    ) -> None:
        """Test that all binary entities can create switch descriptions."""
        for class_code, entities in registry.entities.items():
            for entity in entities:
                # Binary entities have exactly 2 enum_values
                if len(entity.enum_values) != 2:
                    continue

                # Should not raise
                desc = _create_switch_description(class_code, entity)
                assert desc is not None
                assert desc.epc == entity.epc
                assert desc.class_code == class_code
                assert desc.translation_key == entity.id
