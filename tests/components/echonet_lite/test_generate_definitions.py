"""Tests for generate_definitions script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from homeassistant.components.echonet_lite.definitions import (
    BinaryDecoderSpec,
    EntityDefinition,
)
from homeassistant.components.echonet_lite.generator.generate_definitions import (
    DECODERS,
    MRAProperty,
    camel_to_snake,
    determine_entity_type,
    generate_strings,
    parse_mra_property,
)
from homeassistant.components.echonet_lite.switch import _create_switch_description

# ============================================================================
# Tests for camel_to_snake utility function
# ============================================================================


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("camelCase", "camel_case"),
        ("CamelCase", "camel_case"),
        ("camelCaseString", "camel_case_string"),
        ("simple", "simple"),
        ("UPPER", "u_p_p_e_r"),
        ("XMLParser", "x_m_l_parser"),
        ("parseHTML", "parse_h_t_m_l"),
        ("", ""),
        ("a", "a"),
        ("AB", "a_b"),
    ],
)
def test_camel_to_snake(input_str: str, expected: str) -> None:
    """Test camelCase to snake_case conversion."""
    assert camel_to_snake(input_str) == expected


# ============================================================================
# Tests for parse_mra_property function
# ============================================================================


def test_parse_mra_property_basic() -> None:
    """Test basic property parsing."""
    prop_data = {
        "epc": "0xE0",
        "propertyName": {"en": "Temperature", "ja": "温度"},
        "accessRule": {"get": "required", "set": "notApplicable", "inf": "optional"},
        "data": {"type": "number", "format": "int16"},
    }

    result = parse_mra_property(prop_data, {})

    assert result is not None
    assert result.epc == 0xE0
    assert result.name_en == "Temperature"
    assert result.name_ja == "温度"
    assert result.get is True
    assert result.data_type == "number"


def test_parse_mra_property_state_type_with_enum() -> None:
    """Test parsing state type property with enum values."""
    prop_data = {
        "epc": "0xB0",
        "propertyName": {"en": "Operation mode", "ja": "運転モード"},
        "accessRule": {"get": "required", "set": "required", "inf": "required"},
        "data": {
            "type": "state",
            "enum": [
                {
                    "edt": "0x41",
                    "name": "auto",
                    "descriptions": {"en": "Automatic mode"},
                },
                {
                    "edt": "0x42",
                    "name": "cooling",
                    "descriptions": {"en": "Cooling mode"},
                },
                {
                    "edt": "0x43",
                    "name": "heating",
                    "descriptions": {"en": "Heating mode"},
                },
            ],
        },
    }

    result = parse_mra_property(prop_data, {})

    assert result is not None
    assert result.data_type == "state"
    assert result.enum_values == {
        "65": "auto",
        "66": "cooling",
        "67": "heating",
    }
    assert result.enum_descriptions == {
        "auto": "Automatic mode",
        "cooling": "Cooling mode",
        "heating": "Heating mode",
    }


def test_parse_mra_property_with_ref_resolution() -> None:
    """Test parsing property with $ref resolution."""
    prop_data = {
        "epc": "0xB1",
        "propertyName": {"en": "Detection status", "ja": "検知状態"},
        "accessRule": {"get": "required"},
        "data": {"$ref": "#/definitions/state_Detected-NotDetected_4142"},
    }

    definitions = {
        "state_Detected-NotDetected_4142": {
            "type": "state",
            "enum": [
                {"edt": "0x41", "name": "detected"},
                {"edt": "0x42", "name": "notDetected"},
            ],
        }
    }

    result = parse_mra_property(prop_data, definitions)

    assert result is not None
    assert result.data_type == "state"
    assert result.enum_values == {
        "65": "detected",
        "66": "not_detected",
    }


def test_parse_mra_property_access_rules() -> None:
    """Test various access rule combinations."""
    # Test 'required_c' (conditional required)
    prop_data = {
        "epc": "0x80",
        "propertyName": {"en": "Test", "ja": "テスト"},
        "accessRule": {"get": "required_c", "set": "optional", "inf": "notApplicable"},
        "data": {"type": "state"},
    }

    result = parse_mra_property(prop_data, {})

    assert result is not None
    assert result.get is True


def test_parse_mra_property_html_bracket_replacement() -> None:
    """Test HTML-like brackets are replaced in descriptions."""
    prop_data = {
        "epc": "0xB0",
        "propertyName": {"en": "Test", "ja": "テスト"},
        "accessRule": {"get": "required"},
        "data": {
            "type": "state",
            "enum": [
                {
                    "edt": "0x41",
                    "name": "test",
                    "descriptions": {"en": "Value <min> to <max>"},
                },
            ],
        },
    }

    result = parse_mra_property(prop_data, {})

    assert result is not None
    assert result.enum_descriptions["test"] == "Value [min] to [max]"


# ============================================================================
# Tests for determine_entity_type function
# ============================================================================


def test_determine_entity_type_skip_no_get_access() -> None:
    """Test that properties without get access are skipped."""
    prop = MRAProperty(epc=0xE0, get=False)

    result = determine_entity_type(0x0011, 0xE0, prop, "Temperature sensor")

    assert result is None


def test_determine_entity_type_binary_occupancy() -> None:
    """Test binary entity for occupancy detection.

    Note: decoder is auto-inferred from MRA enum_values via _try_state_entity.
    device_class is not explicitly set as 0xB1 relies on auto-inference.
    """
    prop = MRAProperty(
        epc=0xB1, name_en="Human detection status", get=True, data_type="state"
    )

    result = determine_entity_type(0x0007, 0xB1, prop, "Human detection sensor")

    assert result is not None
    platform, attrs = result
    assert platform == "binary"
    # device_class is not set - let Home Assistant infer or user customize
    assert "device_class" not in attrs
    # decoder is now auto-inferred in _try_state_entity
    assert attrs["decoder"] == "binary_on_off"


def test_determine_entity_type_home_ac_multivalue_state_skipped() -> None:
    """Test that multi-value state properties are skipped (no longer supported as select)."""
    prop = MRAProperty(
        epc=0xA1,
        name_en="Automatic control of air flow direction setting",
        get=True,
        data_type="state",
        enum_values={"65": "auto", "66": "non_auto", "67": "auto_vertical"},
    )

    result = determine_entity_type(0x0130, 0xA1, prop, "Home air conditioner")

    # Multi-value states are now skipped (select platform removed)
    assert result is None


def test_determine_entity_type_state_detection_binary() -> None:
    """Test binary entity for state type with detection keyword."""
    prop = MRAProperty(
        epc=0xC0,
        name_en="Leak detection status",
        get=True,
        data_type="state",
        enum_values={"0x41": "detected", "0x42": "not_detected"},
    )

    result = determine_entity_type(0x9999, 0xC0, prop, "Some device")

    assert result is not None
    platform, attrs = result
    assert platform == "binary"
    assert attrs["decoder"] == "binary_on_off"


def test_determine_entity_type_state_multivalue_skipped() -> None:
    """Test that multi-value state properties are skipped (no longer supported as select)."""
    prop = MRAProperty(
        epc=0xC0,
        name_en="Mode setting",
        get=True,
        data_type="state",
        enum_values={"0x41": "mode1", "0x42": "mode2", "0x43": "mode3"},
    )

    result = determine_entity_type(0x9999, 0xC0, prop, "Some device")

    # Multi-value states are now skipped (select platform removed)
    assert result is None


def test_determine_entity_type_operation_status_binary() -> None:
    """Test that operation status (0x80) is resolved as switch with device_class=power."""
    prop = MRAProperty(
        epc=0x80, name_en="Operation status", get=True, data_type="state"
    )

    result = determine_entity_type(0x9999, 0x80, prop, "Some device")

    assert result is not None
    platform, attrs = result
    assert platform == "binary"
    assert attrs.get("device_class") == "power"


# ============================================================================
# Tests for Pydantic models
# ============================================================================


def test_mra_property_model_defaults() -> None:
    """Test MRAProperty model default values."""
    prop = MRAProperty(epc=0xE0)

    assert prop.epc == 0xE0
    assert prop.name_en == ""
    assert prop.name_ja == ""
    assert prop.get is False
    assert prop.data_type is None
    assert prop.enum_values == {}
    assert prop.enum_descriptions == {}


# ============================================================================
# Tests for definition constants
# ============================================================================


def test_decoders_have_valid_types() -> None:
    """Test that all DECODERS have valid type field."""
    valid_types = {"binary"}

    for name, decoder in DECODERS.items():
        assert "type" in decoder, f"Decoder {name} missing 'type' field"
        assert decoder["type"] in valid_types, (
            f"Decoder {name} has invalid type: {decoder['type']}"
        )


def test_binary_decoders_have_on_off() -> None:
    """Test that binary decoders have on/off fields."""
    for name, decoder in DECODERS.items():
        if decoder["type"] == "binary":
            assert "on" in decoder, f"Binary decoder {name} missing 'on' field"
            assert "off" in decoder, f"Binary decoder {name} missing 'off' field"


def test_generate_strings_binary() -> None:
    """Test that binary entities are added to both binary_sensor and switch sections."""
    definitions: dict[str, Any] = {
        "devices": {
            "0x0135": {
                "name_en": "Air cleaner",
                "name_ja": "空気清浄器",
                "entities": [
                    {
                        "platform": "binary",
                        "epc": "0x80",
                        "name_en": "Operation status",
                        "name_ja": "動作状態",
                        "translation_key": "class_0135_power",
                        "device_class": "",
                        "unit": "",
                        "state_class": "",
                        "decoder": "",
                        "enum_values": {},
                    }
                ],
            },
            "0x0007": {
                "name_en": "Human detection sensor",
                "name_ja": "人体検知センサ",
                "entities": [
                    {
                        "platform": "binary",
                        "epc": "0xB1",
                        "name_en": "Human detection status",
                        "name_ja": "人体検知状態",
                        "translation_key": "class_0007_epc_b1",
                        "device_class": "occupancy",
                        "unit": "",
                        "state_class": "",
                        "decoder": "",
                        "enum_values": {},
                    }
                ],
            },
        }
    }

    result = generate_strings(definitions)
    entity_strings = result.get("entity", {})

    # Verify that binary entries are added to switch only (not binary_sensor)
    assert "switch" in entity_strings

    # Check class_0135_power is in switch
    assert "class_0135_power" in entity_strings["switch"]
    assert entity_strings["switch"]["class_0135_power"]["name"] == "Operation status"

    # Check class_0007_epc_b1 is in switch
    assert "class_0007_epc_b1" in entity_strings["switch"]
    assert (
        entity_strings["switch"]["class_0007_epc_b1"]["name"]
        == "Human detection status"
    )


def test_definitions_no_enum_in_binary() -> None:
    """Test that binary platform never uses enum decoder.

    This test prevents regression of the issue where multi-value enums
    were incorrectly assigned to binary platforms that can only handle 2 states.
    """
    definitions_path = (
        Path(__file__).parent.parent.parent.parent
        / "homeassistant"
        / "components"
        / "echonet_lite"
        / "definitions.json"
    )

    with definitions_path.open(encoding="utf-8") as f:
        definitions = json.load(f)

    issues: list[str] = []

    # Check all device entities
    for device_code, device_info in definitions.get("devices", {}).items():
        for entity in device_info.get("entities", []):
            platform = entity.get("platform", "")
            decoder = entity.get("decoder", "")
            epc = entity.get("epc", "")
            enum_count = len(entity.get("enum_values", {}))

            # Rule 1: binary must never use enum decoder
            if platform == "binary" and decoder == "enum":
                issues.append(
                    f"Device {device_code} EPC {epc}: binary cannot use enum decoder"
                )

            # Rule 2: Entities with >2 enum values should not exist (select removed)
            if enum_count > 2:
                issues.append(
                    f"Device {device_code} EPC {epc}: "
                    f"{enum_count} enum values should have been skipped "
                    f"(select platform removed)"
                )

            # Rule 3: binary with 2 enum values should use binary_* decoder
            if (
                platform == "binary"
                and enum_count == 2
                and decoder
                and not decoder.startswith("binary_")
            ):
                issues.append(
                    f"Device {device_code} EPC {epc}: "
                    f"2-value enum should use binary_* decoder, not {decoder}"
                )

    # Assert no issues found
    assert not issues, (
        f"Found {len(issues)} platform-decoder mismatches:\n" + "\n".join(issues)
    )


def test_definitions_decoder_type_consistency() -> None:
    """Test that decoder types are consistent with their platform usage.

    Validates that each decoder type is only used with appropriate platforms:
    - binary_*: only for binary platform
    """
    definitions_path = (
        Path(__file__).parent.parent.parent.parent
        / "homeassistant"
        / "components"
        / "echonet_lite"
        / "definitions.json"
    )

    with definitions_path.open(encoding="utf-8") as f:
        definitions = json.load(f)

    decoder_definitions = definitions.get("decoders", {})
    issues: list[str] = []

    # Map decoder types to allowed platforms
    decoder_type_rules = {
        "binary": ["binary"],
    }

    # Check all device entities
    for device_code, device_info in definitions.get("devices", {}).items():
        for entity in device_info.get("entities", []):
            platform = entity.get("platform", "")
            decoder = entity.get("decoder", "")
            epc = entity.get("epc", "")

            if not decoder or not platform:
                continue

            # Get decoder type from decoder definitions
            decoder_def = decoder_definitions.get(decoder, {})
            decoder_type = decoder_def.get("type", "")

            if not decoder_type:
                continue

            # Check if platform is allowed for this decoder type
            allowed_platforms = decoder_type_rules.get(decoder_type, [])
            if allowed_platforms and platform not in allowed_platforms:
                issues.append(
                    f"Device {device_code} EPC {epc}: "
                    f"decoder '{decoder}' (type: {decoder_type}) "
                    f"used with platform '{platform}', "
                    f"but only allowed with: {', '.join(allowed_platforms)}"
                )

    assert not issues, (
        f"Found {len(issues)} decoder-type inconsistencies:\n" + "\n".join(issues)
    )


def test_no_multivalue_enum_entities_in_definitions() -> None:
    """Test that no entities with 3+ enum values exist (select platform removed).

    This validates that the generator correctly skips multi-value enum properties
    now that select platform is no longer supported.
    """
    definitions_path = (
        Path(__file__).parent.parent.parent.parent
        / "homeassistant"
        / "components"
        / "echonet_lite"
        / "definitions.json"
    )

    with definitions_path.open(encoding="utf-8") as f:
        definitions = json.load(f)

    # Find entities with 3+ enum values
    multivalue_entities: list[dict[str, Any]] = []

    for device_code, device_info in definitions.get("devices", {}).items():
        for entity in device_info.get("entities", []):
            enum_count = len(entity.get("enum_values", {}))
            if enum_count >= 3:
                multivalue_entities.append(
                    {
                        "device_code": device_code,
                        "epc": entity.get("epc", ""),
                        "platform": entity.get("platform", ""),
                        "enum_count": enum_count,
                    }
                )

    assert not multivalue_entities, (
        f"Found {len(multivalue_entities)} entities with 3+ enum values "
        "(should be skipped now that select platform is removed):\n"
        + "\n".join(
            f"  Device {e['device_code']} EPC {e['epc']}: {e['enum_count']} values"
            for e in multivalue_entities
        )
    )


def test_no_null_decoders_in_definitions() -> None:
    """Test that definitions.json contains no entities with null decoders."""
    definitions_path = (
        Path(__file__).parent.parent.parent.parent
        / "homeassistant"
        / "components"
        / "echonet_lite"
        / "definitions.json"
    )

    with definitions_path.open(encoding="utf-8") as f:
        definitions = json.load(f)

    # Check all device entities
    null_decoder_entities: list[dict[str, Any]] = []

    for device_code, device_info in definitions["devices"].items():
        for entity in device_info.get("entities", []):
            decoder = entity.get("decoder")
            if decoder is None or decoder == "null":
                null_decoder_entities.append(
                    {
                        "device_code": device_code,
                        "device_name": device_info.get("name_en", "Unknown"),
                        "epc": entity.get("epc"),
                        "platform": entity.get("platform"),
                    }
                )

    assert not null_decoder_entities, (
        f"Found {len(null_decoder_entities)} entities with null decoder:\n"
        + "\n".join(
            f"  Device {e['device_code']} ({e['device_name']}) "
            f"EPC {e['epc']} platform={e['platform']}"
            for e in null_decoder_entities
        )
    )


# ============================================================================
# Tests for description creation functions
# ============================================================================


def _make_entity_def(
    entity: dict[str, Any], *, platform: str | None = None
) -> EntityDefinition:
    """Create an EntityDefinition from raw entity data (same logic as _parse_entity)."""
    epc = entity["epc"]
    plat = platform or entity.get("platform", "binary")
    translation_key_raw = entity.get("translation_key", "")
    name_en = entity.get("name_en", "")
    byte_offset = entity.get("byte_offset", 0)

    translation_key: str | None = translation_key_raw or None
    fallback_name: str | None = name_en if not translation_key else None

    return EntityDefinition(
        platform=plat,
        epc=epc,
        decoder=entity.get("decoder", ""),
        translation_key=translation_key,
        name_en=name_en,
        name_ja=entity.get("name_ja", ""),
        device_class=entity.get("device_class", ""),
        unit=entity.get("unit", ""),
        state_class=entity.get("state_class", ""),
        enum_values=entity.get("enum_values", {}),
        fallback_name=fallback_name,
        byte_offset=byte_offset,
        byte_count=entity.get("byte_count", 1),
        manufacturer_code=entity.get("manufacturer_code"),
    )


class TestDescriptionCreation:
    """Tests to verify all entity descriptions can be created successfully."""

    @pytest.fixture
    def definitions(self) -> dict[str, Any]:
        """Load definitions.json for tests."""
        definitions_path = Path(__file__).parent.parent.parent.parent / (
            "homeassistant/components/echonet_lite/definitions.json"
        )
        return json.loads(definitions_path.read_text())

    def test_all_switch_descriptions_can_be_created(
        self, definitions: dict[str, Any]
    ) -> None:
        """Test that all switch entities can create descriptions."""

        failed_entities: list[str] = []
        tested_count = 0

        # Get decoder definitions
        decoders = definitions.get("decoders", {})

        for device_code, device_info in definitions["devices"].items():
            class_code = int(device_code)
            for entity in device_info.get("entities", []):
                if entity.get("platform") != "binary":
                    continue

                decoder_name = entity.get("decoder", "")
                decoder_def = decoders.get(decoder_name, {})
                if decoder_def.get("type") != "binary":
                    continue

                tested_count += 1
                entity_def = _make_entity_def(entity)

                # BinaryDecoderSpec expects bytes for on/off values
                on_val = decoder_def.get("on", 0x30)
                off_val = decoder_def.get("off", 0x31)
                decoder_spec = BinaryDecoderSpec(
                    on=bytes([on_val]),
                    off=bytes([off_val]),
                )

                # This should not raise any exceptions
                result = _create_switch_description(
                    class_code, entity_def, decoder_spec
                )
                if result is None:
                    failed_entities.append(
                        f"  Device 0x{class_code:04X} EPC 0x{entity['epc']:02X}: "
                        f"{entity.get('name_en', 'Unknown')}"
                    )

        # Note: switch entities may not exist if no writable binary properties
        # This test passes if either no switch entities exist or all create successfully
        if tested_count > 0:
            assert not failed_entities, (
                f"_create_switch_description returned None for "
                f"{len(failed_entities)} entities:\n" + "\n".join(failed_entities)
            )
