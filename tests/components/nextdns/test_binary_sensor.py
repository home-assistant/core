"""Test binary sensor of NextDNS integration."""
from datetime import timedelta
from unittest.mock import patch

from nextdns import ApiError

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import CONNECTION_STATUS, init_integration

from tests.common import async_fire_time_changed


async def test_binary_Sensor(hass: HomeAssistant) -> None:
    """Test states of the binary sensors."""
    registry = er.async_get(hass)

    await init_integration(hass)

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("binary_sensor.fake_profile_device_connection_status")
    assert entry
    assert entry.unique_id == "xyz12_this_device_nextdns_connection_status"

    state = hass.states.get(
        "binary_sensor.fake_profile_device_profile_connection_status"
    )
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get(
        "binary_sensor.fake_profile_device_profile_connection_status"
    )
    assert entry
    assert entry.unique_id == "xyz12_this_device_profile_connection_status"


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass)

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON

    future = utcnow() + timedelta(minutes=10)
    with patch(
        "homeassistant.components.nextdns.NextDns.connection_status",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=20)
    with patch(
        "homeassistant.components.nextdns.NextDns.connection_status",
        return_value=CONNECTION_STATUS,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.fake_profile_device_connection_status")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON
