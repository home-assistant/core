"""Tests for the ECHONET Lite base entity module.

These tests verify base entity error handling in _async_send_property
and _async_send_properties methods. Uses switch platform as a simple
vehicle to exercise the shared code path.
"""

from __future__ import annotations

from unittest.mock import patch

from pyhems import EOJ, EPC_MANUFACTURER_CODE, EntityDefinition, EnumValue
import pytest

from homeassistant.components.echonet_lite.const import DOMAIN
from homeassistant.components.echonet_lite.entity import (
    can_process_enum_values,
    infer_platform,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_MANUFACTURER_CODE, TestProperty

# Air cleaner class code (0x0135) - simple device with operation status switch
CLASS_CODE_AIR_CLEANER = 0x0135
EPC_OPERATION_STATUS = 0x80


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Enable the switch platform for base entity tests."""
    return [Platform.SWITCH]


async def _setup_switch_device(hass: HomeAssistant, entry) -> str:
    """Set up a switch device (air cleaner) and return the entity_id."""
    coordinator = entry.runtime_data.coordinator

    node_id = "010106"
    eoj = EOJ(0x027901)  # Fuel cell instance 1 (not air cleaner to avoid fan platform)

    # EPC 0x80 in SET property map enables switch entity
    entry.runtime_data.client.get.return_value = [
        TestProperty(epc=0x9E, edt=b"\x01\x80"),  # SET property map: 0x80
        TestProperty(epc=0x9F, edt=b"\x01\x80"),  # GET property map: 0x80
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=EPC_OPERATION_STATUS, edt=b"\x31"),  # off
    ]

    await coordinator.device_manager.setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "010106-027901-80"
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("mock_definitions_registry")
async def test_send_property_address_unknown_raises_error(
    hass: HomeAssistant,
    init_integration,
    mock_echonet_lite_client,
) -> None:
    """Test that error is raised when target node address is unknown."""
    entry = init_integration
    entity_id = await _setup_switch_device(hass, entry)

    # send returns False when address is unknown
    mock_echonet_lite_client.send.return_value = False

    with (
        pytest.raises(HomeAssistantError, match="target node address is unknown"),
        patch.object(
            entry.runtime_data.property_poller,
            "schedule_immediate_poll",
        ),
    ):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )


async def _setup_readonly_switch_device(hass: HomeAssistant, entry) -> str:
    """Set up a switch device where EPC 0x80 is NOT in the SET property map."""
    coordinator = entry.runtime_data.coordinator

    node_id = "010108"
    eoj = EOJ(0x027901)  # Fuel cell instance 1 (not air cleaner)

    # EPC 0x80 NOT in SET property map (0x9E is empty), but in GET property map
    entry.runtime_data.client.get.return_value = [
        TestProperty(epc=0x9E, edt=b"\x00"),  # SET property map: empty
        TestProperty(epc=0x9F, edt=b"\x01\x80"),  # GET property map: 0x80
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=EPC_OPERATION_STATUS, edt=b"\x31"),  # off
    ]

    await coordinator.device_manager.setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "010108-027901-80"
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("mock_definitions_registry")
async def test_send_property_not_writable_raises_error(
    hass: HomeAssistant,
    init_integration,
    mock_echonet_lite_client,
) -> None:
    """Test that writing to a non-writable EPC raises HomeAssistantError."""
    entry = init_integration
    entity_id = await _setup_readonly_switch_device(hass, entry)

    with pytest.raises(HomeAssistantError, match="not writable"):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )

    # Ensure no frame was actually sent
    mock_echonet_lite_client.send.assert_not_awaited()


def test_can_process_enum_values_with_no_duplicates() -> None:
    """Test that clean enum_values returns True."""
    entity = EntityDefinition(
        id="test_entity",
        epc=0x80,
        name_en="Test Entity",
        name_ja="テストエンティティ",
        get="required",
        set="optional",
        enum_values=(
            EnumValue(edt=0x30, key="on", name_en="ON", name_ja="オン"),
            EnumValue(edt=0x31, key="off", name_en="OFF", name_ja="オフ"),
        ),
    )

    assert can_process_enum_values(entity) is True


def test_can_process_enum_values_with_duplicate_key() -> None:
    """Test that duplicate keys returns False."""
    entity = EntityDefinition(
        id="test_entity",
        epc=0x80,
        name_en="Test Entity",
        name_ja="テストエンティティ",
        get="required",
        set="optional",
        enum_values=(
            EnumValue(edt=0x30, key="mode", name_en="Mode A", name_ja="モード A"),
            EnumValue(edt=0x31, key="mode", name_en="Mode B", name_ja="モード B"),
        ),
    )

    assert can_process_enum_values(entity) is False


def test_can_process_enum_values_with_no_enum_values() -> None:
    """Test that numeric entities (no enum_values) return True."""
    entity = EntityDefinition(
        id="test_entity",
        epc=0xB0,
        name_en="Temperature",
        name_ja="温度",
        get="required",
        set="optional",
        enum_values=(),
    )

    assert can_process_enum_values(entity) is True


def test_can_process_enum_values_with_many_unique_values() -> None:
    """Test that many unique enum values returns True."""
    entity = EntityDefinition(
        id="test_entity",
        epc=0xA0,
        name_en="Mode",
        name_ja="モード",
        get="required",
        set="optional",
        enum_values=(
            EnumValue(edt=0x41, key="auto", name_en="Auto", name_ja="自動"),
            EnumValue(edt=0x42, key="cooling", name_en="Cooling", name_ja="冷房"),
            EnumValue(edt=0x43, key="heating", name_en="Heating", name_ja="暖房"),
            EnumValue(edt=0x44, key="dehumidify", name_en="Dehumidify", name_ja="除湿"),
        ),
    )

    assert can_process_enum_values(entity) is True


def test_infer_platform_write_only_with_enum() -> None:
    """Test that write-only entities with enum values are skipped (None).

    Previously mapped to button platform, but button is no longer supported.
    Only switch (writable 2-enum readable) is supported.
    """
    entity = EntityDefinition(
        id="class_0002_epc_bf",
        epc=0xBF,
        name_en="Invasion occurrence status resetting",
        name_ja="侵入発生状態リセット設定",
        get="notApplicable",
        set="optional",
        enum_values=(
            EnumValue(edt=0x00, key="reset", name_en="Reset", name_ja="リセット"),
        ),
    )

    assert infer_platform(entity) is None


def test_infer_platform_write_only_numeric() -> None:
    """Test that write-only numeric entities are skipped (no button).

    Button platform requires exactly 1 enum value (action command).
    Write-only numeric properties without enum_values are skipped.
    """
    entity = EntityDefinition(
        id="test_write_only_numeric",
        epc=0xD0,
        name_en="Test write-only numeric",
        name_ja="テスト書き込み専用数値",
        get="notApplicable",
        set="optional",
        format="uint8",
        enum_values=(),
    )

    assert infer_platform(entity) is None


def test_infer_platform_readable_with_single_enum() -> None:
    """Test that readable entities with single enum value are skipped.

    Single enum values on readable properties are not processable for any
    platform (binary_sensor needs 2, select needs 3+).
    """
    entity = EntityDefinition(
        id="test_readable_single_enum",
        epc=0xE0,
        name_en="Test readable with single enum",
        name_ja="テスト読み取り単一列挙",
        get="required",
        set="optional",
        enum_values=(EnumValue(edt=0x00, key="value", name_en="Value", name_ja="値"),),
    )

    assert infer_platform(entity) is None
