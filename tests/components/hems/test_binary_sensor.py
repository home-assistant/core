"""Tests for the HEMS binary sensor platform."""

from __future__ import annotations

import pytest

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
    """Enable the binary sensor platform for these tests."""

    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_occupancy_status(hass: HomeAssistant, init_integration) -> None:
    """Ensure occupancy sensors surface status correctly."""
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010101").hex()
    eoj = int.from_bytes(bytes.fromhex("026f01"), "big")

    entry.runtime_data.client.async_get.side_effect = [
        [
            TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xE4)),
            TestProperty(
                epc=EPC_MANUFACTURER_CODE,
                edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
            ),
            TestProperty(epc=0xE4, edt=b"\x41"),
        ],
        [
            TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xE4)),
            TestProperty(
                epc=EPC_MANUFACTURER_CODE,
                edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
            ),
            TestProperty(epc=0xE4, edt=b"\x42"),
        ],
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "010101-026f01-e4"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Simulate update via frame event
    update_frame = TestFrame(
        tid=2,
        seoj=eoj.to_bytes(3, "big"),
        deoj=bytes.fromhex("05ff01"),
        esv=0x72,
        properties=[
            TestProperty(epc=0xE4, edt=b"\x42"),
        ],
    )
    await coordinator.async_process_frame_event(
        make_frame_event(
            update_frame,
            received_at=31.0,
            node_id=node_id,
            eoj=eoj,
        ),
    )
    await hass.async_block_till_done()

    state2 = hass.states.get(entity_id)
    assert state2 is not None
    assert state2.state == "off"


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_human_detection_sensor(hass: HomeAssistant, init_integration) -> None:
    """Ensure human detection sensors register under binary_sensor domain."""
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010101").hex()
    eoj = int.from_bytes(bytes.fromhex("000701"), "big")

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xB1)),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0xB1, edt=b"\x41"),
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "010101-000701-b1"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    # Human detection sensor uses auto-inference without explicit device_class
    assert "device_class" not in state.attributes
