"""The tests for the TCP binary sensor platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.binary_sensor import SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

TEST_ENTITY = "binary_sensor.test_name"


async def test_state(
    hass: HomeAssistant,
    mock_socket: MagicMock,
    freezer: FrozenDateTimeFactory,
    setup_tcp,
) -> None:
    """Check the state and the update of the binary sensor."""
    mock_socket.recv.return_value = b"off"
    await setup_tcp(value_on="7.on")
    assert hass.states.get(TEST_ENTITY).state == STATE_OFF

    mock_socket.recv.return_value = b"on"
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(TEST_ENTITY).state == STATE_ON
