"""Tests to verify climate and select entity non-overlap for 0x0130 (Home AC).

This test suite ensures that:
1. EPCs managed exclusively by climate (0xA3 swing mode) are not in definitions.json
2. EPCs managed exclusively by climate are not generated as select entities
3. Select-specific EPCs (0xA4, 0xA5 airflow) are properly generated
4. HOME_AC_CLIMATE_MANAGED_EPCS in generate_definitions.py is maintained correctly
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homeassistant.components.hems.generator.generate_definitions import (
    HOME_AC_CLIMATE_MANAGED_EPCS,
)

# Constants for EPCs used in tests
EPC_OPERATION_STATUS = 0x80
EPC_SWING_AIR_FLOW = 0xA3

DEFINITIONS_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "homeassistant"
    / "components"
    / "hems"
    / "definitions.json"
)


class TestClimateSelectOverlap:
    """Test suite for climate/select EPC non-overlap."""

    @pytest.fixture
    def definitions(self) -> dict:
        """Load definitions.json."""
        with open(DEFINITIONS_PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_0xa3_not_in_definitions(self, definitions: dict) -> None:
        """Verify 0xA3 (swing mode) and 0x80 (on/off) are not in 0x0130 definitions."""
        # Class code is now integer key (0x0130 = 304)
        ac_entities = (
            definitions.get("devices", {}).get(str(0x0130), {}).get("entities", [])
        )
        # EPC is now integer
        epc_list = [e.get("epc") for e in ac_entities]

        assert 0xA3 not in epc_list, (
            "0xA3 (swing mode) should not be in definitions as it's managed by climate"
        )
        assert 0x80 not in epc_list, (
            "0x80 (operation status) should not be in definitions as it's managed by climate"
        )

    def test_0xa4_0xa5_in_definitions(self, definitions: dict) -> None:
        """Verify 0xA4 and 0xA5 (airflow) are in 0x0130 definitions as select."""
        # Class code is now integer key (0x0130 = 304)
        ac_entities = (
            definitions.get("devices", {}).get(str(0x0130), {}).get("entities", [])
        )

        # Map EPC to platform (EPC is now integer)
        epc_to_platform = {e.get("epc"): e.get("platform") for e in ac_entities}

        assert 0xA4 in epc_to_platform, (
            "0xA4 (vertical airflow) should be in definitions"
        )
        assert epc_to_platform[0xA4] == "select", (
            "0xA4 should be select platform (not climate)"
        )

        assert 0xA5 in epc_to_platform, (
            "0xA5 (horizontal airflow) should be in definitions"
        )
        assert epc_to_platform[0xA5] == "select", (
            "0xA5 should be select platform (not climate)"
        )

    def test_no_overlap_between_climate_and_select(self, definitions: dict) -> None:
        """Verify no EPCs are both climate-managed and in select definitions."""
        # Class code is now integer key (0x0130 = 304)
        ac_entities = (
            definitions.get("devices", {}).get(str(0x0130), {}).get("entities", [])
        )

        # EPCs defined as select in definitions (EPC is now integer)
        select_epcs = {
            e.get("epc") for e in ac_entities if e.get("platform") == "select"
        }

        # Climate-managed EPCs should not appear as select
        overlap = HOME_AC_CLIMATE_MANAGED_EPCS & select_epcs
        assert not overlap, (
            f"Climate-managed EPCs {overlap} should not be defined as select"
        )

    def test_climate_managed_epcs_have_specific_values(self) -> None:
        """Verify climate manages all HVAC-related EPCs for 0x0130."""
        # This test documents the current design constraint
        # Climate manages: on/off, fan speed, swing, operation mode, auto temp, target temp
        expected = frozenset({0x80, 0xA0, 0xA3, 0xB0, 0xB1, 0xB3})
        assert expected == HOME_AC_CLIMATE_MANAGED_EPCS, (
            f"Expected climate to manage {expected}, got {HOME_AC_CLIMATE_MANAGED_EPCS}"
        )


class TestClimateEPCSelection:
    """Test that climate EPCs are appropriate for climate entity."""

    def test_climate_managed_epcs_are_correct(self) -> None:
        """Verify 0xA3 (swing mode) and 0x80 (on/off) are the climate-managed EPCs."""
        # 0xA3 = "Automatic swing of air flow setting"
        # 0x80 = "Operation status" (on/off controlled via HVAC mode)
        assert EPC_SWING_AIR_FLOW == 0xA3, "0xA3 is expected to be the swing mode EPC"
        assert EPC_OPERATION_STATUS == 0x80, (
            "0x80 is expected to be the operation status EPC"
        )
        assert EPC_SWING_AIR_FLOW in HOME_AC_CLIMATE_MANAGED_EPCS, (
            "Swing mode EPC should be in HOME_AC_CLIMATE_MANAGED_EPCS"
        )
        assert EPC_OPERATION_STATUS in HOME_AC_CLIMATE_MANAGED_EPCS, (
            "Operation status EPC should be in HOME_AC_CLIMATE_MANAGED_EPCS"
        )

    def test_0xa4_0xa5_are_select_only_airflow(self) -> None:
        """Verify 0xA4 and 0xA5 are airflow EPCs that can't be expressed as climate modes."""
        # These are manual airflow control and cannot be expressed in climate entity
        # (climate only supports swing_mode, not individual vertical/horizontal control)

        # They should NOT be in climate-managed EPCs
        assert 0xA4 not in HOME_AC_CLIMATE_MANAGED_EPCS
        assert 0xA5 not in HOME_AC_CLIMATE_MANAGED_EPCS
