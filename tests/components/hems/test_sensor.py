"""Tests for the HEMS sensor platform."""

from __future__ import annotations

import pytest

from homeassistant.components.hems.const import (
    DOMAIN,
    EPC_GET_PROPERTY_MAP,
    EPC_MANUFACTURER_CODE,
)
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import TEST_MANUFACTURER_CODE, make_frame_event, make_property_map_edt
from .helpers import TestFrame, TestProperty


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Enable the sensor platform for these tests."""

    return [Platform.SENSOR]


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_temperature_sensor_state(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Ensure temperature sensors surface decoded values."""
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010102").hex()
    seoj = bytes.fromhex("001101")
    eoj = int.from_bytes(seoj, "big")

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xE0)),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0xE0, edt=b"\x00d"),
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "010102-001101-e0_0"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10.0"
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS

    device_registry = dr.async_get(hass)
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device is not None
    assert device.name is not None
    assert "HEMS" in device.name or device.identifiers


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_temperature_sensor_immeasurable(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Ensure temperature sensors return unknown for special ECHONET values.

    ECHONET Lite defines special values for temperature:
    - 0x7E (126): Immeasurable
    - 0x7F (127): Overflow
    - 0x80 (-128 signed): Underflow
    """
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010106").hex()
    seoj = bytes.fromhex("013001")  # Home air conditioner
    eoj = int.from_bytes(seoj, "big")

    # 0xBE is outdoor temperature with signed_byte_temperature decoder
    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xBE)),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0xBE, edt=b"\x7e"),  # TEMP_IMMEASURABLE = 0x7E (126)
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "010106-013001-be_0"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    # Should be unknown/unavailable instead of "126"
    assert state.state == "unknown"


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_humidity_sensor_updates(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Ensure humidity sensors track subsequent updates."""
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010103").hex()
    seoj = bytes.fromhex("001201")
    eoj = int.from_bytes(seoj, "big")

    entry.runtime_data.client.async_get.side_effect = [
        [
            TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xE0)),
            TestProperty(
                epc=EPC_MANUFACTURER_CODE,
                edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
            ),
            TestProperty(epc=0xE0, edt=b"\x32"),
        ],
        [
            TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xE0)),
            TestProperty(
                epc=EPC_MANUFACTURER_CODE,
                edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
            ),
            TestProperty(epc=0xE0, edt=b"\x28"),
        ],
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "010103-001201-e0_0"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "50"

    # Simulate update via frame event
    update_frame = TestFrame(
        tid=2,
        seoj=seoj,
        deoj=bytes.fromhex("05ff01"),
        esv=0x72,
        properties=[
            TestProperty(epc=0xE0, edt=b"\x28"),
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
    assert state2.state == "40"


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_battery_instantaneous_charge_discharge_power(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Ensure battery instantaneous charge/discharge power sensors work."""
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010104").hex()
    seoj = bytes.fromhex("027d01")
    eoj = int.from_bytes(seoj, "big")

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xD3, 0xE4)),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0xD3, edt=b"\x00\x00\x04\xb0"),
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "010104-027d01-d3_0"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1200"


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_battery_remaining_capacity_percent(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Ensure battery remaining capacity percent sensors work."""
    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010105").hex()
    seoj = bytes.fromhex("027d01")
    eoj = int.from_bytes(seoj, "big")

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=EPC_GET_PROPERTY_MAP, edt=make_property_map_edt(0xD3, 0xE4)),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0xE4, edt=b"\x50"),
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "010105-027d01-e4_0"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "80"
