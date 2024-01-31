"""Test the Tessie sensor platform."""
from datetime import timedelta

from homeassistant.components.tessie import PLATFORMS
from homeassistant.components.tessie.coordinator import TESSIE_SYNC_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .common import (
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
    TEST_VEHICLE_STATUS_ASLEEP,
    setup_platform,
)

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=TESSIE_SYNC_INTERVAL)


async def test_coordinator_online(
    hass: HomeAssistant, mock_get_state, mock_get_status
) -> None:
    """Tests that the coordinator handles online vehicles."""

    await setup_platform(hass, PLATFORMS)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_status.assert_called_once()
    mock_get_state.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_ON


async def test_coordinator_asleep(hass: HomeAssistant, mock_get_status) -> None:
    """Tests that the coordinator handles asleep vehicles."""

    await setup_platform(hass, [Platform.BINARY_SENSOR])
    mock_get_status.return_value = TEST_VEHICLE_STATUS_ASLEEP

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_status.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_OFF


async def test_coordinator_clienterror(hass: HomeAssistant, mock_get_status) -> None:
    """Tests that the coordinator handles client errors."""

    mock_get_status.side_effect = ERROR_UNKNOWN
    await setup_platform(hass, [Platform.BINARY_SENSOR])

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_status.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_UNAVAILABLE


async def test_coordinator_auth(hass: HomeAssistant, mock_get_status) -> None:
    """Tests that the coordinator handles timeout errors."""

    mock_get_status.side_effect = ERROR_AUTH
    await setup_platform(hass, [Platform.BINARY_SENSOR])

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_status.assert_called_once()


async def test_coordinator_connection(hass: HomeAssistant, mock_get_status) -> None:
    """Tests that the coordinator handles connection errors."""

    mock_get_status.side_effect = ERROR_CONNECTION
    await setup_platform(hass, [Platform.BINARY_SENSOR])
    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    mock_get_status.assert_called_once()
    assert hass.states.get("binary_sensor.test_status").state == STATE_UNAVAILABLE
