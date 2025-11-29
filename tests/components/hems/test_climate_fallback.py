"""Tests for the HEMS climate platform fallback logic."""

from __future__ import annotations

import pytest

from homeassistant.components.hems.climate import (
    _CLIMATE_REQUIRED_EPCS,
    CLASS_CODE_HOME_AIR_CONDITIONER,
)
from homeassistant.components.hems.const import (
    DOMAIN,
    EPC_GET_PROPERTY_MAP,
    EPC_MANUFACTURER_CODE,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_MANUFACTURER_CODE, make_frame_event, make_property_map_edt
from .helpers import TestFrame, TestProperty


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Enable the climate platform for these tests."""

    return [Platform.CLIMATE]


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_climate_target_temp_fallback(
    hass: HomeAssistant, init_integration
) -> None:
    """Ensure climate entities fall back to 0xB3 if 0xB5/0xB6 are not supported."""

    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010104").hex()
    seoj = bytes.fromhex("013001")
    eoj = int.from_bytes(seoj, "big")

    # Create device that lacks a required EPC (0xB3)
    required_epcs = _CLIMATE_REQUIRED_EPCS.get(
        CLASS_CODE_HOME_AIR_CONDITIONER, frozenset()
    )

    property_map_frame = TestFrame(
        tid=0,
        seoj=seoj,
        deoj=bytes.fromhex("0ef001"),
        esv=0x72,
        properties=[
            TestProperty(
                epc=EPC_GET_PROPERTY_MAP,
                # Required EPCs omit 0xB3 -> should reject entity creation
                edt=make_property_map_edt(*sorted(required_epcs - {0xB3})),
            ),
            TestProperty(
                epc=EPC_MANUFACTURER_CODE,
                edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
            ),
        ],
    )
    await coordinator.async_process_frame_event(
        make_frame_event(
            property_map_frame,
            received_at=9.0,
            node_id=node_id,
            eoj=eoj,
        ),
    )
    await hass.async_block_till_done()

    # Send status: COOL mode (0x42), Target Temp 0xB3 = 25C (0x19)
    frame = TestFrame(
        tid=1,
        seoj=seoj,
        deoj=bytes.fromhex("0ef001"),
        esv=0x73,
        properties=[
            TestProperty(epc=0x80, edt=b"\x30"),  # ON
            TestProperty(epc=0xB0, edt=b"\x42"),  # COOL
            TestProperty(epc=0xB3, edt=b"\x19"),  # 25C
            TestProperty(epc=0xBB, edt=b"\x1e"),  # Room 30C
        ],
    )
    await coordinator.async_process_frame_event(
        make_frame_event(
            frame,
            received_at=10.0,
            node_id=node_id,
            eoj=eoj,
        ),
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    # 必須EPC不足なのでエンティティは生成されない
    entity_id = entity_registry.async_get_entity_id(
        "climate", DOMAIN, "010104-013001-home_air_conditioner"
    )
    assert entity_id is None
