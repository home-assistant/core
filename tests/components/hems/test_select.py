"""Tests for the HEMS select platform."""

from __future__ import annotations

import pytest

from homeassistant.components.hems.const import DOMAIN, EPC_MANUFACTURER_CODE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_MANUFACTURER_CODE, make_frame_event, make_property_map_edt
from .helpers import TestFrame, TestProperty


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Enable the select platform for these tests."""

    return [Platform.SELECT]


@pytest.mark.usefixtures("mock_definitions_registry")
async def test_select_air_flow_direction(
    hass: HomeAssistant, init_integration, mock_hems_client
) -> None:
    """Test select entities for air conditioner airflow direction (0x0130).

    Validates creation from property maps, option decoding, and writing EDTs.
    """

    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    # Initial async_get response with property maps and current select values
    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=0x9E, edt=make_property_map_edt(0xA1, 0xA4, 0xA5)),
        TestProperty(epc=0x9F, edt=make_property_map_edt(0xA1, 0xA4, 0xA5)),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0xA1, edt=b"\x41"),  # auto
        TestProperty(epc=0xA4, edt=b"\x41"),  # uppermost
        TestProperty(epc=0xA5, edt=b"\x51"),  # right
    ]

    await coordinator._async_setup_device("010106", int("013001", 16))
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "select", DOMAIN, "010106-013001-a1"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "auto"
    assert "non_auto" in state.attributes["options"]

    mock_hems_client.async_send.reset_mock()

    # Select another option and ensure correct EDT is sent
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "auto_horizontal"},
        blocking=True,
    )

    assert mock_hems_client.async_send.await_count == 1
    frame_arg = mock_hems_client.async_send.await_args_list[0].args[1]
    assert frame_arg.properties[0].epc == 0xA1
    assert frame_arg.properties[0].edt == b"\x44"  # auto_horizontal
    assert frame_arg.deoj == bytes.fromhex("013001")
    assert frame_arg.esv == 0x61

    # Simulate device update to non_auto via frame event
    update_frame = TestFrame(
        tid=2,
        seoj=bytes.fromhex("013001"),
        deoj=bytes.fromhex("05ff01"),
        esv=0x72,
        properties=[TestProperty(epc=0xA1, edt=b"\x42")],
    )
    await coordinator.async_process_frame_event(
        make_frame_event(
            update_frame,
            received_at=31.0,
            node_id="010106",
            eoj=int("013001", 16),
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "non_auto"
