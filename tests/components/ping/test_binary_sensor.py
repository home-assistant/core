"""The test for the ping binary_sensor platform."""

from datetime import timedelta

from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def test_binary_sensor(
    hass: HomeAssistant, load_yaml_integration: None, mock_ping: None
) -> None:
    """Test setup from yaml."""

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    state_binary_sensor = hass.states.get("binary_sensor.test_binary_sensor")
    assert state_binary_sensor.state == STATE_ON
