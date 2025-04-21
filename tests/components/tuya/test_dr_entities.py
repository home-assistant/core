"""Tests for Tuya device category 'dr' ( Heated Blanket ).

This module validates that:
- All expected DPCodes are defined in the DPCode enum.
- The 'dr' category is properly mapped in the SWITCHES and SELECTS platform constants.
- Required string translations for UI display exist in strings.json.
- A complete integration flow using a device fixture results in the correct
  number and types of entities being created and registered in Home Assistant.

This test module enforces internal consistency between Tuya device specifications,
entity descriptions, UI translations, and integration behavior. It also serves as a
regression guard to catch breaking changes in schema mappings or platform definitions
that could impact /standard instruction set/ for electric blanket .
"""

import json
from pathlib import Path

import pytest

import homeassistant.components.tuya as tuya_pkg
from homeassistant.components.tuya.const import (
    DOMAIN as TUYA_DOMAIN,
    TUYA_DISCOVERY_NEW,
    DPCode,
    DPType,
)
from homeassistant.components.tuya.select import SELECTS
from homeassistant.components.tuya.switch import SWITCHES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .common import make_customer_device

from tests.common import MockConfigEntry

# All DPCode switch keys for the blanket
BLANKET_SWITCH_KEYS = [
    "SWITCH",
    "SWITCH_1",
    "SWITCH_2",
    "PREHEAT",
    "PREHEAT_1",
    "PREHEAT_2",
]

# All DPCode select keys for the blanket
BLANKET_SELECT_KEYS = [
    "LEVEL",
    "LEVEL_1",
    "LEVEL_2",
]


def test_dpcode_contains_all_blanket_keys() -> None:
    """Ensure all DPCodes exist in const.DPCode enum."""
    for key in BLANKET_SWITCH_KEYS:
        assert key in DPCode.__members__, f"Missing DPCode.{key}"
    for key in BLANKET_SELECT_KEYS:
        assert key in DPCode.__members__, f"Missing DPCode.{key}"


def test_select_and_switch_descriptions_for_dr() -> None:
    """Ensure all keys are defined in SELECTS and SWITCHES."""
    select_keys = {desc.key for desc in SELECTS.get("dr", ())}
    switch_keys = {desc.key for desc in SWITCHES.get("dr", ())}

    for dp in (DPCode.LEVEL, DPCode.LEVEL_1, DPCode.LEVEL_2):
        assert dp in select_keys, f"Missing select description for {dp}"
    for dp in (
        DPCode.SWITCH,
        DPCode.SWITCH_1,
        DPCode.SWITCH_2,
        DPCode.PREHEAT,
        DPCode.PREHEAT_1,
        DPCode.PREHEAT_2,
    ):
        assert dp in switch_keys, f"Missing switch description for {dp}"


def test_strings_json_translations_for_blanket() -> None:
    """strings.json must have translations required for the integration."""

    data = json.loads(
        (Path(tuya_pkg.__file__).parent / "strings.json").read_text(encoding="utf-8")
    )
    sel = data["entity"]["select"]
    sw = data["entity"]["switch"]

    for key in (
        "electric_blanket_level",
        "electric_blanket_level_side_a",
        "electric_blanket_level_side_b",
    ):
        assert key in sel, f"Missing select translation {key}"
        states = sel[key]["state"]
        for lvl in (f"level_{i}" for i in range(1, 11)):
            assert lvl in states, f"{key}.state missing {lvl}"

    for key in (
        "power",
        "side_a_power",
        "side_b_power",
        "preheat",
        "side_a_preheat",
        "side_b_preheat",
    ):
        assert key in sw, f"Missing switch translation {key}"
        assert "name" in sw[key], f"No name for switch.{key}"


@pytest.mark.asyncio
async def test_dr_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tuya_manager,
) -> None:
    """End-to-end: loading the device fixture yields all entities."""
    # Load the full JSON fixture for ‘dr’
    device = make_customer_device("heated_blanket_dr.json")
    device.online = True

    # Set up integration
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire discovery
    mock_tuya_manager.device_map = {device.id: device}
    async_dispatcher_send(hass, TUYA_DISCOVERY_NEW, [device.id])
    await hass.async_block_till_done()

    # Device registered?
    dev_reg = dr.async_get(hass)
    dev = dev_reg.async_get_device({(TUYA_DOMAIN, device.id)})
    assert dev, "Device not in registry"
    assert dev.name == device.name, "Device name mismatch"

    # Entities created? - Count
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_device(ent_reg, dev.id)
    domains = {e.domain for e in entries}
    assert "select" in domains, "Selects not created"
    assert "switch" in domains, "Switches not created"
    assert len(entries) == len(device.function), (
        "Entries mismatch between device and registry"
    )

    # Match spec entries to observed entries.
    # - Switches
    expected_switch_dpcodes = {
        key.lower()
        for key, val in device.function.items()
        if val.type == DPType.BOOLEAN
    }
    sw_entries = [e for e in entries if e.domain == "switch"]
    found = {e.unique_id.removeprefix(f"tuya.{device.id}") for e in sw_entries}
    assert found == expected_switch_dpcodes

    # - Selects
    expected_select_dpcodes = {
        key.lower() for key, val in device.function.items() if val.type == DPType.ENUM
    }
    select_entries = [e for e in entries if e.domain == "select"]
    found = {e.unique_id.removeprefix(f"tuya.{device.id}") for e in select_entries}
    assert found == expected_select_dpcodes
