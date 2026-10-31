"""Test EcoNet emergency-heat controls."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from pyeconet.equipment import Equipment
import pytest

from homeassistant.components import switch
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

pytestmark = [
    pytest.mark.parametrize("platform", [Platform.SWITCH]),
    pytest.mark.parametrize("equipment_data", ["thermostat_controls"], indirect=True),
]
ENTITY_ID = "switch.thermostat_emergency_heat"


@pytest.mark.parametrize(
    ("service", "mode", "expected"),
    [(SERVICE_TURN_ON, 5, STATE_ON), (SERVICE_TURN_OFF, 1, STATE_OFF)],
)
async def test_emergency_heat(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_api: MagicMock,
    mock_equipment: Equipment,
    service: str,
    mode: int,
    expected: str,
) -> None:
    """Send emergency-heat commands and reflect reported operating modes."""
    await setup_integration()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    await hass.services.async_call(
        switch.DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_api.publish.assert_called_once_with(
        {"@MODE": mode}, "thermostat_1", "serial_2"
    )
    mock_equipment.update_equipment_info(
        {"device_name": "thermostat_1", "@MODE": {"value": mode}}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == expected


async def test_no_emergency_heat(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    equipment_data: dict,
) -> None:
    """Do not create an emergency-heat switch when the mode is unsupported."""
    equipment_data["@MODE"]["constraints"]["enumText"] = ["Off", "Heating", "Cooling"]
    await setup_integration()
    assert hass.states.async_all(switch.DOMAIN) == []
