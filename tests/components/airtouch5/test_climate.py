"""Tests for the Airtouch5 climate platform."""

from unittest.mock import AsyncMock

from airtouch5py.packets.ac_status import AcFanSpeed

from homeassistant.components.climate import ATTR_FAN_MODE, FAN_AUTO
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

AC_ENTITY_ID = "climate.ac_1"


async def test_ac_fan_speed_not_available(
    hass: HomeAssistant,
    mock_airtouch5_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the AC fan mode is unknown when the fan speed is not available."""

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(AC_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO

    status = mock_airtouch5_client.latest_ac_status[1]
    status.ac_fan_speed = AcFanSpeed.NOT_AVAILABLE
    for callback in mock_airtouch5_client.ac_status_callbacks:
        callback({1: status})
    await hass.async_block_till_done()

    state = hass.states.get(AC_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_FAN_MODE] is None
