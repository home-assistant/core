"""Tests for the Airtouch5 climate platform."""

from unittest.mock import AsyncMock

from airtouch5py.packets.ac_status import AcFanSpeed, AcMode
import pytest

from homeassistant.components.climate import ATTR_FAN_MODE, FAN_AUTO, HVACMode
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

AC_ENTITY_ID = "climate.ac_1"


@pytest.mark.parametrize(
    ("ac_mode", "ac_fan_speed", "expected_state", "expected_fan_mode"),
    [
        pytest.param(
            AcMode.AUTO,
            AcFanSpeed.NOT_AVAILABLE,
            HVACMode.AUTO,
            None,
            id="fan_speed_not_available",
        ),
        pytest.param(
            AcMode.NOT_AVAILABLE,
            AcFanSpeed.AUTO,
            STATE_UNKNOWN,
            FAN_AUTO,
            id="mode_not_available",
        ),
    ],
)
async def test_ac_status_not_available(
    hass: HomeAssistant,
    mock_airtouch5_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    ac_mode: AcMode,
    ac_fan_speed: AcFanSpeed,
    expected_state: str,
    expected_fan_mode: str | None,
) -> None:
    """Test the AC when its mode or fan speed is not available."""

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(AC_ENTITY_ID)
    assert state
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO

    status = mock_airtouch5_client.latest_ac_status[1]
    status.ac_mode = ac_mode
    status.ac_fan_speed = ac_fan_speed
    for callback in mock_airtouch5_client.ac_status_callbacks:
        callback({1: status})
    await hass.async_block_till_done()

    state = hass.states.get(AC_ENTITY_ID)
    assert state
    assert state.state == expected_state
    assert state.attributes[ATTR_FAN_MODE] == expected_fan_mode
