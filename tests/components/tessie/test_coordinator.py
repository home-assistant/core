"""Test the Tessie sensor platform."""
from datetime import timedelta

from homeassistant.components.tessie.coordinator import TESSIE_SYNC_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .common import (
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
    TEST_VEHICLE_STATE_ASLEEP,
    TEST_VEHICLE_STATE_ONLINE,
    setup_platform,
)

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=TESSIE_SYNC_INTERVAL)


async def test_coordinator_online(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles online vehicles."""

    mock_get_state.return_value = TEST_VEHICLE_STATE_ONLINE
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_ON


async def test_coordinator_asleep(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles asleep vehicles."""

    mock_get_state.return_value = TEST_VEHICLE_STATE_ASLEEP
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_OFF


async def test_coordinator_clienterror(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles client errors."""

    mock_get_state.side_effect = ERROR_UNKNOWN
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_UNAVAILABLE


async def test_coordinator_auth(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles timeout errors."""

    mock_get_state.side_effect = ERROR_AUTH
    await setup_platform(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()


async def test_coordinator_connection(hass: HomeAssistant, mock_get_state) -> None:
    """Tests that the coordinator handles connection errors."""

    mock_get_state.side_effect = ERROR_CONNECTION
    await setup_platform(hass)
    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_state.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_UNAVAILABLE
