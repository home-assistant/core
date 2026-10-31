"""Test EcoNet fan-mode selection."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from pyeconet.equipment import Equipment
import pytest

from homeassistant.components import select
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.parametrize("platform", [Platform.SELECT])
ENTITY_ID = "select.thermostat_fan_mode"


@pytest.mark.parametrize("equipment_data", ["thermostat_controls"], indirect=True)
async def test_fan_mode(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_api: MagicMock,
    mock_equipment: Equipment,
) -> None:
    """Expose fan options, select a mode, and receive its reported state."""
    await setup_integration()
    state = hass.states.get(ENTITY_ID)
    assert state.state == "AUTO"
    assert state.attributes[select.ATTR_OPTIONS] == ["AUTO", "ON_CONTINUOUS"]
    await hass.services.async_call(
        select.DOMAIN,
        select.SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, select.ATTR_OPTION: "ON_CONTINUOUS"},
        blocking=True,
    )
    mock_api.publish.assert_called_once_with(
        {"@FANMODE": 1}, "thermostat_1", "serial_2"
    )
    mock_equipment.update_equipment_info(
        {"device_name": "thermostat_1", "@FANMODE": {"value": 1}}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "ON_CONTINUOUS"


@pytest.mark.parametrize("equipment_data", ["thermostat"], indirect=True)
async def test_unsupported_fan_mode(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
) -> None:
    """Do not create a selector for a thermostat without fan-mode support."""
    await setup_integration()
    assert hass.states.async_all(select.DOMAIN) == []
