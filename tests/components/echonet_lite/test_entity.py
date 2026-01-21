"""Tests for the ECHONET Lite base entity module.

These tests verify base entity error handling in _async_send_property
and _async_send_properties methods. Uses switch platform as a simple
vehicle to exercise the shared code path.
"""

from __future__ import annotations

from unittest.mock import patch

from pyhems import EOJ
import pytest

from homeassistant.components.echonet_lite.const import DOMAIN, EPC_MANUFACTURER_CODE
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
    eoj = EOJ(0x013501)  # Air cleaner instance 1

    # EPC 0x80 in SET property map enables switch entity
    entry.runtime_data.client.async_get.return_value = [
        TestProperty(epc=0x9E, edt=b"\x01\x80"),  # SET property map: 0x80
        TestProperty(epc=0x9F, edt=b"\x01\x80"),  # GET property map: 0x80
        TestProperty(
            epc=EPC_MANUFACTURER_CODE,
            edt=TEST_MANUFACTURER_CODE.to_bytes(3, "big"),
        ),
        TestProperty(epc=EPC_OPERATION_STATUS, edt=b"\x31"),  # off
    ]

    await coordinator._async_setup_device(node_id, eoj)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, "010106-013501-80"
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("mock_definitions_registry")
async def test_send_property_oserror_raises_home_assistant_error(
    hass: HomeAssistant,
    init_integration,
    mock_echonet_lite_client,
) -> None:
    """Test that OSError during send is converted to HomeAssistantError."""
    entry = init_integration
    entity_id = await _setup_switch_device(hass, entry)

    mock_echonet_lite_client.async_send.side_effect = OSError("Network is unreachable")

    with pytest.raises(HomeAssistantError, match="Failed to send ECHONET Lite command"):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_definitions_registry")
async def test_send_property_address_unknown_raises_error(
    hass: HomeAssistant,
    init_integration,
    mock_echonet_lite_client,
) -> None:
    """Test that error is raised when target node address is unknown."""
    entry = init_integration
    entity_id = await _setup_switch_device(hass, entry)

    # async_send returns False when address is unknown
    mock_echonet_lite_client.async_send.return_value = False

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
