"""Tests for the ECHONET Lite switch platform."""

from __future__ import annotations

from pyhems import EOJ
import pytest

from homeassistant.components.echonet_lite.const import DOMAIN, EPC_MANUFACTURER_CODE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_MANUFACTURER_CODE, TestFrame, TestProperty, make_frame_event


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Enable the switch platform for these tests."""

    return [Platform.SWITCH]


@pytest.mark.usefixtures("mock_definitions_registry")
async def test_operation_status_switch(
    hass: HomeAssistant,
    init_integration,
    mock_echonet_lite_client,
) -> None:
    """Test operation status switch for air cleaner (0x0135) device.

    This tests that:
    - Switch entity is created when EPC 0x80 is in SET property map
    - State is correctly decoded (0x30=on, 0x31=off)
    - Turn on/off service calls send correct commands
    """
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    entry.runtime_data.client.async_get.side_effect = [
        [
            TestProperty(epc=0x9E, edt=b"\x01\x80"),
            TestProperty(epc=0x9F, edt=b"\x01\x80"),
            TestProperty(
                epc=EPC_MANUFACTURER_CODE,
                edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
            ),
            TestProperty(epc=0x80, edt=b"\x31"),
        ],
        [
            TestProperty(epc=0x9E, edt=b"\x01\x80"),
            TestProperty(epc=0x9F, edt=b"\x01\x80"),
            TestProperty(
                epc=EPC_MANUFACTURER_CODE,
                edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
            ),
            TestProperty(epc=0x80, edt=b"\x30"),
        ],
    ]

    await coordinator._async_setup_device("010106", EOJ(0x013501))
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "010106-013501-80"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Reset mock for explicit service call test
    mock_echonet_lite_client.async_send.reset_mock()

    # Test turn_on service call
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_echonet_lite_client.async_send.await_count == 1
    call = mock_echonet_lite_client.async_send.await_args_list[0]
    # async_send(node_id, frame)
    frame_arg = call.args[1]
    assert frame_arg.properties[0].epc == 0x80
    assert frame_arg.properties[0].edt == b"\x30"  # 0x30 = on
    assert frame_arg.deoj == EOJ(0x013501)
    assert frame_arg.esv == 0x61  # SetC
    assert call.args[0] == "010106"

    # Simulate update via frame event
    update_frame = TestFrame(
        tid=2,
        seoj=bytes.fromhex("013501"),
        deoj=bytes.fromhex("05ff01"),
        esv=0x72,
        properties=[
            TestProperty(epc=0x80, edt=b"\x30"),
        ],
    )
    await coordinator.async_process_frame_event(
        make_frame_event(
            update_frame,
            received_at=31.0,
            node_id="010106",
            eoj=EOJ(int("013501", 16)),
        ),
    )
    await hass.async_block_till_done()

    state2 = hass.states.get(entity_id)
    assert state2 is not None
    assert state2.state == "on"

    # Reset mock and test turn_off service call
    mock_echonet_lite_client.async_send.reset_mock()

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_echonet_lite_client.async_send.await_count == 1
    call = mock_echonet_lite_client.async_send.await_args_list[0]
    frame_arg = call.args[1]
    assert frame_arg.properties[0].epc == 0x80
    assert frame_arg.properties[0].edt == b"\x31"  # 0x31 = off
