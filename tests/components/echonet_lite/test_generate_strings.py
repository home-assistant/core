"""Tests for generate_strings.py - HA-specific strings.json generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyhems import (
    DefinitionsRegistry,
    EntityDefinition,
    EnumValue,
    load_definitions_registry,
)
import pytest

from homeassistant.components.echonet_lite.entity import infer_platform
from homeassistant.components.echonet_lite.generator.generate_strings import (
    _add_entity_string,
    _build_reverse_lookup,
    _escape_html_brackets,
    _load_common_states,
    _process_entity,
    _resolve_by_name,
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
def common_states() -> dict[str, str]:
    """Load common::state translations."""
    return _load_common_states()


@pytest.fixture
def reverse_lookup(common_states: dict[str, str]) -> dict[str, str]:
    """Build reverse lookup from common states."""
    return _build_reverse_lookup(common_states)


@pytest.fixture
def strings() -> dict[str, Any]:
    """Load strings.json."""
    with open(STRINGS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# Tests for helper functions
# ============================================================================


class TestLoadCommonStates:
    """Test _load_common_states helper function."""

    def test_load_common_states_returns_dict(self) -> None:
        """Test that common states are loaded as a dictionary."""
        states = _load_common_states()
        assert isinstance(states, dict)
        assert len(states) > 0

    def test_load_common_states_has_expected_keys(self) -> None:
        """Test that common states contain expected keys."""
        states = _load_common_states()
        for key in ("on", "off", "auto", "high", "low", "medium", "normal"):
            assert key in states


class TestResolveByName:
    """Test _resolve_by_name helper function."""

    def test_name_match_returns_reference(self) -> None:
        """Test name_en match returns key reference."""
        common_states = {"open": "Open", "closed": "Closed"}
        reverse = _build_reverse_lookup(common_states)
        assert _resolve_by_name("Open", reverse) == "[%key:common::state::open%]"
        assert _resolve_by_name("Closed", reverse) == ("[%key:common::state::closed%]")

    def test_case_insensitive_name_match(self) -> None:
        """Test case-insensitive name_en matching."""
        common_states = {"yes": "Yes", "no": "No"}
        reverse = _build_reverse_lookup(common_states)
        assert _resolve_by_name("YES", reverse) == "[%key:common::state::yes%]"
        assert _resolve_by_name("NO", reverse) == "[%key:common::state::no%]"

    def test_no_match_returns_raw(self) -> None:
        """Test no match returns raw text."""
        common_states = {"on": "On"}
        reverse = _build_reverse_lookup(common_states)
        assert _resolve_by_name("Detected", reverse) == "Detected"


class TestBuildReverseLookup:
    """Test _build_reverse_lookup helper function."""

    def test_builds_lowercase_mapping(self) -> None:
        """Test reverse lookup maps lowercase text to key."""
        common_states = {"auto": "Auto", "on": "On", "off": "Off"}
        reverse = _build_reverse_lookup(common_states)
        assert reverse["auto"] == "auto"
        assert reverse["on"] == "on"
        assert reverse["off"] == "off"

    def test_last_key_wins_on_duplicate(self) -> None:
        """Test last key wins when values collide in dict comprehension."""
        common_states = {"first": "Same", "second": "Same"}
        reverse = _build_reverse_lookup(common_states)
        assert reverse["same"] == "second"


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
            get="required",
            set="notApplicable",
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
            get="required",
            set="optional",
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

    def test_process_binary_entity_writable_creates_switch(
        self,
        reverse_lookup: dict[str, str],
    ) -> None:
        """Test processing writable binary entity creates switch strings only."""
        entity_strings: dict[str, dict[str, dict[str, Any]]] = {}
        entity = EntityDefinition(
            id="operation_status",
            epc=0x80,
            name_en="Operation status",
            name_ja="動作状態",
            get="required",
            set="optional",
            enum_values=(
                EnumValue(edt=0x30, key="true", name_en="ON", name_ja="オン"),
                EnumValue(edt=0x31, key="false", name_en="OFF", name_ja="オフ"),
            ),
        )
        _process_entity(
            entity_strings,
            entity,
            reverse_lookup,
        )

        # Writable binary entity creates only switch strings
        assert "switch" in entity_strings
        assert "binary_sensor" not in entity_strings
        assert "operation_status" in entity_strings["switch"]
        # ON/OFF match common::state::on/off (case-insensitive)
        assert entity_strings["switch"]["operation_status"]["state"]["on"] == (
            "[%key:common::state::on%]"
        )
        assert entity_strings["switch"]["operation_status"]["state"]["off"] == (
            "[%key:common::state::off%]"
        )

    def test_process_entity_with_duplicate_key_skipped(
        self,
        reverse_lookup: dict[str, str],
    ) -> None:
        """Test that entities with duplicate keys are skipped."""
        entity_strings: dict[str, dict[str, dict[str, Any]]] = {}
        entity = EntityDefinition(
            id="bad_entity_duplicate_key",
            epc=0x93,
            name_en="Bad Entity",
            name_ja="不正なエンティティ",
            get="required",
            set="optional",
            enum_values=(
                EnumValue(
                    edt=0x41,
                    key="true",
                    name_en="Not through public",
                    name_ja="公衆網未経由",
                ),
                EnumValue(
                    edt=0x42,
                    key="false",
                    name_en="Through public",
                    name_ja="公衆網経由",
                ),
                EnumValue(
                    edt=0x61,
                    key="true",
                    name_en="Communication OK (no public)",
                    name_ja="通信OK（公衆網なし）",
                ),
                EnumValue(
                    edt=0x62,
                    key="false",
                    name_en="Communication OK (possible)",
                    name_ja="通信OK（公衆網可）",
                ),
            ),
        )
        _process_entity(
            entity_strings,
            entity,
            reverse_lookup,
        )

        # Entity should be skipped - no strings added
        assert entity_strings == {}

    def test_process_non_switch_entity_skipped(
        self,
        reverse_lookup: dict[str, str],
    ) -> None:
        """Test that non-switch entities (read-only, write-only, numeric) are skipped."""
        entity_strings: dict[str, dict[str, dict[str, Any]]] = {}
        # Read-only binary (would have been binary_sensor)
        entity = EntityDefinition(
            id="fault_status",
            epc=0x88,
            name_en="Fault status",
            name_ja="異常発生状態",
            get="required",
            set="notApplicable",
            enum_values=(
                EnumValue(edt=0x41, key="true", name_en="Fault", name_ja="異常あり"),
                EnumValue(
                    edt=0x42, key="false", name_en="No fault", name_ja="異常なし"
                ),
            ),
        )
        _process_entity(entity_strings, entity, reverse_lookup)
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

        # Compare switch entity section only
        generated_entities = generated.get("entity", {}).get("switch", {})
        current_entities = strings.get("entity", {}).get("switch", {})

        assert generated_entities == current_entities, (
            "strings.json switch section does not match generated output. "
            "Run 'python -m homeassistant.components.echonet_lite.generator.generate_strings' "
            "to regenerate."
        )


# ============================================================================
# Tests for definitions-strings consistency
# ============================================================================


class TestDefinitionsStringsConsistency:
    """Test that all definitions have corresponding strings entries."""

    def test_all_writable_binary_entities_have_switch_strings(
        self, registry: DefinitionsRegistry, strings: dict[str, Any]
    ) -> None:
        """Test that writable binary entities have corresponding switch strings."""
        switch_strings = strings.get("entity", {}).get("switch", {})

        for class_code, entities in registry.entities.items():
            for entity in entities:
                if infer_platform(entity) != "switch":
                    continue

                assert entity.id in switch_strings, (
                    f"Writable binary entity for class {class_code} EPC {entity.epc} "
                    f"id '{entity.id}' missing switch string entry"
                )


# ============================================================================
# Tests for entity description creation
# ============================================================================


class TestSwitchDescriptionCreation:
    """Test that switch entity descriptions can be created from definitions."""

    def test_all_switch_entities_create_valid_descriptions(
        self, registry: DefinitionsRegistry
    ) -> None:
        """Test that all switch entities can create switch descriptions."""
        for class_code, entities in registry.entities.items():
            for entity in entities:
                if infer_platform(entity) != "switch":
                    continue

                # Should not raise
                desc = _create_switch_description(class_code, entity)
                assert desc is not None
                assert desc.epc == entity.epc
                assert desc.class_code == class_code
                assert desc.translation_key == entity.id
