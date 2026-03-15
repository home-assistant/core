"""Tests for the ECHONET Lite switch platform."""

from __future__ import annotations

from pyhems import EOJ, EPC_MANUFACTURER_CODE
import pytest

from homeassistant.components.echonet_lite.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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

    entry.runtime_data.client.get.side_effect = [
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

    await coordinator.device_manager.setup_device("010106", EOJ(0x027901))
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "010106-027901-80"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Reset mock for explicit service call test
    mock_echonet_lite_client.set_properties.reset_mock()

    # Test turn_on service call
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_echonet_lite_client.set_properties.await_count == 1
    call = mock_echonet_lite_client.set_properties.await_args_list[0]
    assert call.kwargs["node_id"] == "010106"
    assert call.kwargs["deoj"] == EOJ(0x027901)
    assert call.kwargs["properties"][0].epc == 0x80
    assert call.kwargs["properties"][0].edt == b"\x30"  # 0x30 = on

    # Simulate update via frame event
    update_frame = TestFrame(
        tid=2,
        seoj=bytes.fromhex("027901"),
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
            eoj=EOJ(int("027901", 16)),
        ),
    )
    await hass.async_block_till_done()

    state2 = hass.states.get(entity_id)
    assert state2 is not None
    assert state2.state == "on"

    # Reset mock and test turn_off service call
    mock_echonet_lite_client.set_properties.reset_mock()

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert mock_echonet_lite_client.set_properties.await_count == 1
    call = mock_echonet_lite_client.set_properties.await_args_list[0]
    assert call.kwargs["properties"][0].epc == 0x80
    assert call.kwargs["properties"][0].edt == b"\x31"  # 0x31 = off


@pytest.mark.usefixtures("mock_definitions_registry", "mock_echonet_lite_client")
async def test_switch_created_for_climate_class(
    hass: HomeAssistant, init_integration
) -> None:
    """Test that switch entity IS created for climate class (0x0130).

    Air conditioners no longer have a dedicated climate platform, so EPC 0x80
    (operation status) is handled as a regular switch entity.
    """
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    entry.runtime_data.client.get.return_value = [
        TestProperty(epc=0x9E, edt=b"\x01\x80"),
        TestProperty(epc=0x9F, edt=b"\x01\x80"),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0x80, edt=b"\x30"),
    ]

    await coordinator.device_manager.setup_device("010107", EOJ(0x013001))
    await hass.async_block_till_done()

    # Verify switch entity was created for the air conditioner
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "010107-013001-80"
    )
    assert entity_id is not None


@pytest.mark.usefixtures("mock_definitions_registry")
async def test_switch_not_writable_raises_error(
    hass: HomeAssistant, init_integration, mock_echonet_lite_client
) -> None:
    """Test that turning on a switch with non-writable EPC raises an error.

    When EPC 0x80 is in GET property map but NOT in SET property map,
    the switch entity should be created (for display) but writing should fail.
    """
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    # EPC 0x80 NOT in SET property map, but in GET property map
    entry.runtime_data.client.get.return_value = [
        TestProperty(epc=0x9E, edt=b"\x00"),  # SET property map: empty
        TestProperty(epc=0x9F, edt=b"\x01\x80"),  # GET property map: 0x80
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0x80, edt=b"\x31"),  # off
    ]

    await coordinator.device_manager.setup_device("010108", EOJ(0x027901))
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "010108-027901-80"
    )
    assert entity_id is not None

    with pytest.raises(HomeAssistantError, match="not writable"):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_echonet_lite_client.set_properties.assert_not_awaited()
