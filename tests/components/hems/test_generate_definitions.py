"""Tests for generate_definitions script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from homeassistant.components.hems.binary_sensor import (
    _create_binary_sensor_description,
)
from homeassistant.components.hems.definitions import (
    BinaryDecoderSpec,
    EntityDefinition,
    EnumDecoderSpec,
    NumericDecoderSpec,
)
from homeassistant.components.hems.generator.generate_definitions import (
    DECODERS,
    HOME_AC_CLIMATE_MANAGED_EPCS,
    MRAProperty,
    camel_to_snake,
    determine_entity_type,
    generate_strings,
    parse_mra_property,
)
from homeassistant.components.hems.select import _create_select_description
from homeassistant.components.hems.sensor import _create_sensor_description
from homeassistant.components.hems.switch import _create_switch_description

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
    prop = MRAProperty(epc=0xE0, get=False, set=True)

    result = determine_entity_type(0x0011, 0xE0, prop, "Temperature sensor")

    assert result is None


def test_determine_entity_type_temperature_sensor() -> None:
    """Test temperature sensor entity type determination."""
    prop = MRAProperty(
        epc=0xE0,
        name_en="Temperature",
        get=True,
        data_type="number",
        mra_format="int16",
        mra_unit="Celsius",
        mra_multiple_of=0.1,
    )

    result = determine_entity_type(0x0011, 0xE0, prop, "Temperature sensor")

    assert result is not None
    platform, attrs = result
    assert platform == "sensor"
    assert attrs["device_class"] == "temperature"
    assert attrs["unit"] == "°C"
    assert attrs["decoder"] == "signed_tenths_temperature"


def test_determine_entity_type_humidity_sensor() -> None:
    """Test humidity sensor entity type determination."""
    prop = MRAProperty(
        epc=0xE0,
        name_en="Humidity",
        get=True,
        data_type="number",
        mra_format="uint8",
        mra_unit="%",
    )

    result = determine_entity_type(0x0012, 0xE0, prop, "Humidity sensor")

    assert result is not None
    platform, attrs = result
    assert platform == "sensor"
    assert attrs["device_class"] == "humidity"
    assert attrs["unit"] == "%"


def test_determine_entity_type_binary_sensor_occupancy() -> None:
    """Test binary sensor for occupancy detection.

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


def test_determine_entity_type_common_power_sensor() -> None:
    """Test that EPC 0x84 is NOT handled by determine_entity_type.

    Common power sensors (0x84, 0x85) are expanded by the generator
    using COMMON_SENSOR_PROPERTIES, not via determine_entity_type.
    """
    prop = MRAProperty(epc=0x84, name_en="Power consumption", get=True)

    # determine_entity_type should return None for 0x84
    # as it's handled as a common property by the generator
    result = determine_entity_type(0x9999, 0x84, prop, "Some device")

    # Not handled by determine_entity_type (handled as common property)
    assert result is None


def test_determine_entity_type_home_ac_sensor() -> None:
    """Test home air conditioner sensor entities."""
    prop = MRAProperty(
        epc=0xBB,
        name_en="Room temperature",
        get=True,
        data_type="number",
        mra_format="int8",
        mra_unit="Celsius",
    )

    result = determine_entity_type(0x0130, 0xBB, prop, "Home air conditioner")

    assert result is not None
    platform, attrs = result
    assert platform == "sensor"
    assert attrs["device_class"] == "temperature"


def test_determine_entity_type_home_ac_select() -> None:
    """Test home air conditioner select entities (auto-inferred from state+setting)."""
    prop = MRAProperty(
        epc=0xA1,
        name_en="Automatic control of air flow direction setting",
        get=True,
        data_type="state",
        enum_values={"65": "auto", "66": "non_auto", "67": "auto_vertical"},
    )

    result = determine_entity_type(0x0130, 0xA1, prop, "Home air conditioner")

    assert result is not None
    platform, _ = result
    assert platform == "select"


def test_determine_entity_type_home_ac_climate_managed_skipped() -> None:
    """Test that climate-managed EPCs are skipped for home AC."""
    for epc in HOME_AC_CLIMATE_MANAGED_EPCS:
        prop = MRAProperty(epc=epc, name_en="Test", get=True)
        result = determine_entity_type(0x0130, epc, prop, "Home air conditioner")
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


def test_determine_entity_type_state_multivalue_select() -> None:
    """Test select entity for state type with 3+ enum values."""
    prop = MRAProperty(
        epc=0xC0,
        name_en="Mode setting",
        get=True,
        data_type="state",
        enum_values={"0x41": "mode1", "0x42": "mode2", "0x43": "mode3"},
    )

    result = determine_entity_type(0x9999, 0xC0, prop, "Some device")

    assert result is not None
    platform, attrs = result
    assert platform == "select"
    assert attrs["decoder"] == "enum"


def test_determine_entity_type_operation_status_binary() -> None:
    """Test that operation status (0x80) is resolved as binary_sensor with device_class=power."""
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
    valid_types = {"signed", "unsigned", "temperature", "binary", "enum"}

    for name, decoder in DECODERS.items():
        assert "type" in decoder, f"Decoder {name} missing 'type' field"
        assert decoder["type"] in valid_types, (
            f"Decoder {name} has invalid type: {decoder['type']}"
        )


def test_numeric_decoders_have_bytes_and_scale() -> None:
    """Test that numeric decoders have bytes and scale fields."""
    numeric_types = {"signed", "unsigned", "temperature"}

    for name, decoder in DECODERS.items():
        if decoder["type"] in numeric_types:
            assert "bytes" in decoder, f"Numeric decoder {name} missing 'bytes' field"
            assert "scale" in decoder, f"Numeric decoder {name} missing 'scale' field"
            assert 1 <= decoder["bytes"] <= 4, (
                f"Decoder {name} has invalid bytes: {decoder['bytes']}"
            )


def test_state_decoders_have_on_off() -> None:
    """Test that state decoders have on/off fields."""
    for name, decoder in DECODERS.items():
        if decoder["type"] == "state":
            assert "on" in decoder, f"State decoder {name} missing 'on' field"
            assert "off" in decoder, f"State decoder {name} missing 'off' field"


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
            "0x0011": {
                "name_en": "Temperature sensor",
                "name_ja": "温度センサ",
                "entities": [
                    {
                        "platform": "sensor",
                        "epc": "0xE0",
                        "name_en": "Measured temperature value",
                        "name_ja": "温度計測値",
                        "translation_key": "class_0011_epc_e0",
                        "device_class": "temperature",
                        "unit": "°C",
                        "state_class": "measurement",
                        "decoder": "signed_tenths",
                        "enum_values": {},
                    }
                ],
            },
        }
    }

    result = generate_strings(definitions)
    entity_strings = result.get("entity", {})

    # Verify that binary entries are added to both binary_sensor and switch
    assert "binary_sensor" in entity_strings
    assert "switch" in entity_strings
    assert "sensor" in entity_strings

    # Check class_0135_power is in both binary_sensor and switch
    assert "class_0135_power" in entity_strings["binary_sensor"]
    assert "class_0135_power" in entity_strings["switch"]
    assert (
        entity_strings["binary_sensor"]["class_0135_power"]["name"]
        == "Operation status"
    )
    assert entity_strings["switch"]["class_0135_power"]["name"] == "Operation status"

    # Check class_0007_epc_b1 is in both binary_sensor and switch
    assert "class_0007_epc_b1" in entity_strings["binary_sensor"]
    assert "class_0007_epc_b1" in entity_strings["switch"]
    assert (
        entity_strings["binary_sensor"]["class_0007_epc_b1"]["name"]
        == "Human detection status"
    )
    assert (
        entity_strings["switch"]["class_0007_epc_b1"]["name"]
        == "Human detection status"
    )

    # Check that sensor entries are only in sensor section
    assert "class_0011_epc_e0" in entity_strings["sensor"]
    assert "class_0011_epc_e0" not in entity_strings.get("binary_sensor", {})
    assert "class_0011_epc_e0" not in entity_strings.get("switch", {})


def test_generate_strings_preserves_existing_sensor_entries() -> None:
    """Test that sensor entries from device-specific definitions are generated.

    Since common entities are now expanded into each device, strings
    are generated from device-specific entities only.
    """
    definitions: dict[str, Any] = {
        "devices": {
            "0x0002": {
                "name_en": "Test Device",
                "entities": [
                    {
                        "platform": "sensor",
                        "epc": "0x84",
                        "name_en": "Instantaneous power consumption",
                        "translation_key": "class_common_epc_84",
                    },
                    {
                        "platform": "sensor",
                        "epc": "0x85",
                        "name_en": "Cumulative power consumption",
                        "translation_key": "class_common_epc_85",
                    },
                ],
            }
        },
    }

    result = generate_strings(definitions)
    entity_strings = result.get("entity", {})

    # Verify that common sensor entries are present (shared across all device classes)
    assert "sensor" in entity_strings
    assert "class_common_epc_84" in entity_strings["sensor"]
    assert "class_common_epc_85" in entity_strings["sensor"]
    # Name comes from the mock data's name_en field
    assert (
        entity_strings["sensor"]["class_common_epc_84"]["name"]
        == "Instantaneous power consumption"
    )
    assert (
        entity_strings["sensor"]["class_common_epc_85"]["name"]
        == "Cumulative power consumption"
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
        / "hems"
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

            # Rule 2: Entities with >2 enum values must use select platform
            if enum_count > 2 and platform == "binary":
                issues.append(
                    f"Device {device_code} EPC {epc}: "
                    f"{enum_count} enum values cannot be used with binary platform, "
                    f"should be 'select'"
                )

            # Rule 3: binary with 2 enum values should use binary_* decoder
            if (
                platform == "binary"
                and enum_count == 2
                and decoder
                not in [
                    "binary_on_off",
                    "binary_on_off_30_31",
                    "binary_on_off_41_40",
                    "binary_on_off_41_42",
                ]
                and decoder != ""  # Allow empty decoder for common entities
            ):
                issues.append(
                    f"Device {device_code} EPC {epc}: "
                    f"2-value enum should use binary_* decoder, not {decoder}"
                )

    # Check common entities
    for entity in definitions.get("common", []):
        platform = entity.get("platform", "")
        decoder = entity.get("decoder", "")
        epc = entity.get("epc", "")
        enum_count = len(entity.get("enum_values", {}))

        if platform == "binary" and decoder == "enum":
            issues.append(f"Common EPC {epc}: binary cannot use enum decoder")

    # Assert no issues found
    assert not issues, (
        f"Found {len(issues)} platform-decoder mismatches:\n" + "\n".join(issues)
    )


def test_definitions_decoder_type_consistency() -> None:
    """Test that decoder types are consistent with their platform usage.

    Validates that each decoder type is only used with appropriate platforms:
    - enum: only for select platform
    - binary_*: only for binary platform
    - unsigned/signed: only for sensor platform
    - temperature: only for sensor platform
    """
    definitions_path = (
        Path(__file__).parent.parent.parent.parent
        / "homeassistant"
        / "components"
        / "hems"
        / "definitions.json"
    )

    with definitions_path.open(encoding="utf-8") as f:
        definitions = json.load(f)

    decoder_definitions = definitions.get("decoders", {})
    issues: list[str] = []

    # Map decoder types to allowed platforms
    decoder_type_rules = {
        "enum": ["select"],
        "binary": ["binary"],
        "unsigned": ["sensor"],
        "signed": ["sensor"],
        "temperature": ["sensor"],
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

    # Check common entities
    for entity in definitions.get("common", []):
        platform = entity.get("platform", "")
        decoder = entity.get("decoder", "")
        epc = entity.get("epc", "")

        if not decoder or not platform:
            continue

        decoder_def = decoder_definitions.get(decoder, {})
        decoder_type = decoder_def.get("type", "")

        if not decoder_type:
            continue

        allowed_platforms = decoder_type_rules.get(decoder_type, [])
        if allowed_platforms and platform not in allowed_platforms:
            issues.append(
                f"Common EPC {epc}: "
                f"decoder '{decoder}' (type: {decoder_type}) "
                f"used with platform '{platform}', "
                f"but only allowed with: {', '.join(allowed_platforms)}"
            )

    assert not issues, (
        f"Found {len(issues)} decoder-type inconsistencies:\n" + "\n".join(issues)
    )


@pytest.mark.parametrize(
    ("enum_count", "expected_platform", "expected_decoder_type"),
    [
        # Note: enum_count=2 is not tested here because binary entities
        # don't include enum_values in definitions.json (decoder handles ON/OFF).
        # The logic is tested in test_determine_entity_type_state_detection_binary.
        (3, "select", "enum"),
        (4, "select", "enum"),
        (5, "select", "enum"),
        (6, "select", "enum"),
    ],
)
def test_enum_value_count_determines_platform(
    enum_count: int, expected_platform: str, expected_decoder_type: str
) -> None:
    """Test that enum value count correctly determines platform assignment.

    This validates the auto-decoder inference logic:
    - 2 values -> binary with binary decoder
    - 3+ values -> select with enum decoder
    """
    definitions_path = (
        Path(__file__).parent.parent.parent.parent
        / "homeassistant"
        / "components"
        / "hems"
        / "definitions.json"
    )

    with definitions_path.open(encoding="utf-8") as f:
        definitions = json.load(f)

    decoder_definitions = definitions.get("decoders", {})

    # Find entities with matching enum count
    matching_entities = [
        {
            "device_code": device_code,
            "epc": entity.get("epc", ""),
            "platform": entity.get("platform", ""),
            "decoder": entity.get("decoder", ""),
            "enum_count": enum_count,
        }
        for device_code, device_info in definitions.get("devices", {}).items()
        for entity in device_info.get("entities", [])
        if len(entity.get("enum_values", {})) == enum_count
    ]

    # Skip if no entities found with this enum count
    if not matching_entities:
        pytest.skip(f"No entities found with {enum_count} enum values")

    # Validate all matching entities
    issues: list[str] = []
    for entity in matching_entities:
        platform = entity["platform"]
        decoder = entity["decoder"]
        decoder_def = decoder_definitions.get(decoder, {})
        decoder_type = decoder_def.get("type", "")

        if platform != expected_platform:
            issues.append(
                f"Device {entity['device_code']} EPC {entity['epc']}: "
                f"{enum_count} enum values should use '{expected_platform}' platform, "
                f"but uses '{platform}'"
            )

        if decoder_type != expected_decoder_type:
            issues.append(
                f"Device {entity['device_code']} EPC {entity['epc']}: "
                f"{enum_count} enum values should use '{expected_decoder_type}' decoder type, "
                f"but uses '{decoder_type}' ({decoder})"
            )

    assert not issues, f"Found {len(issues)} issues:\n" + "\n".join(issues)


def test_no_null_decoders_in_definitions() -> None:
    """Test that definitions.json contains no entities with null decoders."""
    definitions_path = (
        Path(__file__).parent.parent.parent.parent
        / "homeassistant"
        / "components"
        / "hems"
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

    # Check common entities
    for entity in definitions.get("common", []):
        decoder = entity.get("decoder")
        if decoder is None or decoder == "null":
            null_decoder_entities.append(
                {
                    "device_code": "common",
                    "device_name": "Common",
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


def test_no_enum_in_binary() -> None:
    """Test that binary platform never uses enum decoder.

    Regression test for issue where multi-value enum (3+ values) was assigned
    to binary platform, which only supports 2-state (ON/OFF).
    Such entities should use select platform instead.
    """
    definitions_path = (
        Path(__file__).parent.parent.parent.parent
        / "homeassistant"
        / "components"
        / "hems"
        / "definitions.json"
    )

    with definitions_path.open(encoding="utf-8") as f:
        definitions = json.load(f)

    # Find all binary entities using enum
    problematic_entities: list[dict[str, Any]] = []

    for device_code, device_info in definitions["devices"].items():
        for entity in device_info.get("entities", []):
            if entity.get("platform") == "binary":
                decoder = entity.get("decoder")
                if decoder == "enum":
                    enum_count = len(entity.get("enum_values", {}))
                    problematic_entities.append(
                        {
                            "device_code": device_code,
                            "device_name": device_info.get("name_en", "Unknown"),
                            "epc": entity.get("epc"),
                            "name_en": entity.get("name_en", ""),
                            "decoder": decoder,
                            "enum_count": enum_count,
                        }
                    )

    # Check common entities too
    for entity in definitions.get("common", []):
        if entity.get("platform") == "binary":
            decoder = entity.get("decoder")
            if decoder == "enum":
                enum_count = len(entity.get("enum_values", {}))
                problematic_entities.append(
                    {
                        "device_code": "common",
                        "device_name": "Common",
                        "epc": entity.get("epc"),
                        "name_en": entity.get("name_en", ""),
                        "decoder": decoder,
                        "enum_count": enum_count,
                    }
                )

    assert not problematic_entities, (
        f"Found {len(problematic_entities)} binary entities "
        "using enum decoder (should use select platform instead):\n"
        + "\n".join(
            f"  Device {e['device_code']} ({e['device_name']}) "
            f"EPC {e['epc']}: {e['name_en']} "
            f"({e['enum_count']} enum values)"
            for e in problematic_entities
        )
    )

    assert not problematic_entities, (
        f"Found {len(problematic_entities)} binary entities "
        "using state_enum decoder (should use select platform instead):\n"
        + "\n".join(
            f"  Device {e['device_code']} ({e['device_name']}) "
            f"EPC {e['epc']}: {e['name_en']} "
            f"({e['enum_count']} enum values)"
            for e in problematic_entities
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
    plat = platform or entity.get("platform", "sensor")
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
            "homeassistant/components/hems/definitions.json"
        )
        return json.loads(definitions_path.read_text())

    def test_all_select_descriptions_can_be_created(
        self, definitions: dict[str, Any]
    ) -> None:
        """Test that all select entities in definitions.json can create descriptions.

        This ensures _create_select_description never returns None for valid entities.
        """
        failed_entities: list[str] = []
        tested_count = 0

        for device_code, device_info in definitions["devices"].items():
            class_code = int(device_code)
            for entity in device_info.get("entities", []):
                if entity.get("platform") != "select":
                    continue

                tested_count += 1
                entity_def = _make_entity_def(entity)

                # Create decoder spec for enum
                decoder_spec = EnumDecoderSpec()

                result = _create_select_description(
                    class_code, entity_def, decoder_spec
                )
                if result is None:
                    failed_entities.append(
                        f"  Device 0x{class_code:04X} EPC 0x{entity['epc']:02X}: "
                        f"{entity.get('name_en', 'Unknown')} "
                        f"(enum_values: {len(entity.get('enum_values', {}))})"
                    )

        assert tested_count > 0, "No select entities found to test"
        assert not failed_entities, (
            f"_create_select_description returned None for {len(failed_entities)} entities:\n"
            + "\n".join(failed_entities)
        )

    def test_all_binary_sensor_descriptions_can_be_created(
        self, definitions: dict[str, Any]
    ) -> None:
        """Test that all binary sensor entities can create descriptions."""
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
                result = _create_binary_sensor_description(
                    class_code, entity_def, decoder_spec
                )
                if result is None:
                    failed_entities.append(
                        f"  Device 0x{class_code:04X} EPC 0x{entity['epc']:02X}: "
                        f"{entity.get('name_en', 'Unknown')}"
                    )

        assert tested_count > 0, "No binary sensor entities found to test"
        assert not failed_entities, (
            f"_create_binary_sensor_description returned None for "
            f"{len(failed_entities)} entities:\n" + "\n".join(failed_entities)
        )

    def test_all_sensor_descriptions_can_be_created(
        self, definitions: dict[str, Any]
    ) -> None:
        """Test that all sensor entities can create descriptions."""
        failed_entities: list[str] = []
        tested_count = 0

        # Get decoder definitions
        decoders = definitions.get("decoders", {})

        # NumericDecoderSpec handles these types
        numeric_types = {"unsigned", "signed", "temperature"}

        for device_code, device_info in definitions["devices"].items():
            class_code = int(device_code)
            for entity in device_info.get("entities", []):
                if entity.get("platform") != "sensor":
                    continue

                decoder_name = entity.get("decoder", "")
                decoder_def = decoders.get(decoder_name, {})
                if decoder_def.get("type") not in numeric_types:
                    continue

                tested_count += 1
                entity_def = _make_entity_def(entity)

                # Create NumericDecoderSpec based on decoder type
                decoder_type = decoder_def.get("type", "unsigned")
                byte_count = decoder_def.get("byte_count", 1)
                scale = decoder_def.get("scale", 1.0)
                decoder_spec = NumericDecoderSpec(
                    type=decoder_type,
                    byte_count=byte_count,
                    scale=scale if scale is not None else 1.0,
                )

                # This should not raise any exceptions
                result = _create_sensor_description(
                    class_code, entity_def, decoder_spec
                )
                if result is None:
                    failed_entities.append(
                        f"  Device 0x{class_code:04X} EPC 0x{entity['epc']:02X}: "
                        f"{entity.get('name_en', 'Unknown')}"
                    )

        assert tested_count > 0, "No sensor entities found to test"
        assert not failed_entities, (
            f"_create_sensor_description returned None for "
            f"{len(failed_entities)} entities:\n" + "\n".join(failed_entities)
        )

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
                if entity.get("platform") != "switch":
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

    def test_select_entities_have_enum_values(
        self, definitions: dict[str, Any]
    ) -> None:
        """Ensure all select entities have non-empty enum_values."""
        empty_enum_entities: list[str] = []

        for device_code, device_info in definitions["devices"].items():
            class_code = int(device_code)
            for entity in device_info.get("entities", []):
                if entity.get("platform") != "select":
                    continue

                enum_values = entity.get("enum_values", {})
                if not enum_values:
                    empty_enum_entities.append(
                        f"  Device 0x{class_code:04X} EPC 0x{entity['epc']:02X}: "
                        f"{entity.get('name_en', 'Unknown')}"
                    )

        assert not empty_enum_entities, (
            f"Found {len(empty_enum_entities)} select entities with empty enum_values:\n"
            + "\n".join(empty_enum_entities)
        )
