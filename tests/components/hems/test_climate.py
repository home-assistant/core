"""Tests for the HEMS climate platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.hems.climate import (
    _CLIMATE_REQUIRED_EPCS,
    CLASS_CODE_HOME_AIR_CONDITIONER,
)
from homeassistant.components.hems.const import (
    DOMAIN,
    EPC_GET_PROPERTY_MAP,
    EPC_MANUFACTURER_CODE,
    EPC_SET_PROPERTY_MAP,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_MANUFACTURER_CODE, make_property_map_edt
from .helpers import TestProperty


@pytest.fixture(name="platforms")
def platforms_fixture() -> list[Platform]:
    """Enable the climate platform for these tests."""

    return [Platform.CLIMATE]


@pytest.mark.usefixtures("mock_definitions_registry", "mock_hems_client")
async def test_climate_entity_state(hass: HomeAssistant, init_integration) -> None:
    """Ensure climate entities expose temperatures and modes."""

    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010104").hex()
    seoj = bytes.fromhex("013001")
    eoj = int.from_bytes(seoj, "big")

    required_epcs = _CLIMATE_REQUIRED_EPCS.get(
        CLASS_CODE_HOME_AIR_CONDITIONER, frozenset()
    )
    advertised_epcs = required_epcs | {0xB5, 0xB6}

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(
            epc=EPC_GET_PROPERTY_MAP,
            edt=make_property_map_edt(*sorted(advertised_epcs)),
        ),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0x80, edt=b"\x30"),
        TestProperty(epc=0xB0, edt=b"\x42"),
        TestProperty(epc=0xB3, edt=b"\x18"),
        TestProperty(epc=0xBB, edt=b"\x1e"),
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "climate", DOMAIN, "010104-013001-climate"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes.get("current_temperature") == 30
    assert state.attributes.get("temperature") == 24


@pytest.mark.usefixtures("mock_definitions_registry")
async def test_set_hvac_mode_sends_commands(
    hass: HomeAssistant,
    init_integration,
    mock_hems_client,
) -> None:
    """Ensure hvac mode changes emit the expected frames."""

    entry = init_integration
    coordinator = entry.runtime_data.coordinator

    node_id = bytes.fromhex("010104").hex()
    seoj = bytes.fromhex("013001")
    eoj = int.from_bytes(seoj, "big")

    required_epcs = _CLIMATE_REQUIRED_EPCS.get(
        CLASS_CODE_HOME_AIR_CONDITIONER, frozenset()
    )
    # Include HEAT-specific target so heat commands prefer 0xB6
    advertised_epcs = required_epcs | {0xB6}
    set_epcs = {0x80, 0xB0}

    entry.runtime_data.client.async_get.return_value = [
        TestProperty(
            epc=EPC_GET_PROPERTY_MAP,
            edt=make_property_map_edt(*sorted(advertised_epcs)),
        ),
        TestProperty(
            epc=EPC_SET_PROPERTY_MAP,
            edt=make_property_map_edt(*sorted(set_epcs)),
        ),
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=0x80, edt=b"\x30"),
        TestProperty(epc=0xB0, edt=b"\x42"),
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "climate", DOMAIN, "010104-013001-climate"
    )
    assert entity_id is not None

    mock_hems_client.async_send.reset_mock()
    with patch.object(
        entry.runtime_data.property_poller,
        "schedule_immediate_poll",
    ) as mock_schedule:
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )
        mock_schedule.assert_called_once_with("010104-013001")
    # Now sends mode and ON together in one call
    assert mock_hems_client.async_send.await_count == 1
    call = mock_hems_client.async_send.await_args_list[0]
    # Check that frame has 2 properties: mode and ON
    assert len(call.args[1].properties) == 2
    # Mode should be 0x43 (HEAT)
    assert call.args[1].properties[0].epc == 0xB0
    assert call.args[1].properties[0].edt == b"\x43"
    # ON should be 0x30
    assert call.args[1].properties[1].epc == 0x80
    assert call.args[1].properties[1].edt == b"\x30"

    mock_hems_client.async_send.reset_mock()
    with patch.object(
        entry.runtime_data.property_poller,
        "schedule_immediate_poll",
    ) as mock_schedule:
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": entity_id, "hvac_mode": HVACMode.OFF},
            blocking=True,
        )
        mock_schedule.assert_called_once_with("010104-013001")
    # OFF sends only operation status
    assert mock_hems_client.async_send.await_count == 1
    off_call = mock_hems_client.async_send.await_args_list[0]
    assert off_call.args[1].properties[0].epc == 0x80
    assert off_call.args[1].properties[0].edt == b"\x31"
