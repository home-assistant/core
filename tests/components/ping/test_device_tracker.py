"""The test for the ping device_tracker platform."""

from datetime import timedelta

from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def test_device_tracker(
    hass: HomeAssistant,
    load_yaml_integration: None,
    mock_ping: None,
    yaml_devices: None,
) -> None:
    """Test setup from yaml."""

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    state_tracker = hass.states.get("device_tracker.test_device_tracker")

    assert state_tracker.state == STATE_HOME
