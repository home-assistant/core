"""Tests for the Amcrest binary sensor platform."""

from unittest.mock import patch

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest.const import SERVICE_EVENT, SERVICE_UPDATE
from homeassistant.components.amcrest.helpers import service_signal
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from .conftest import _MockAmcrestAPI, setup_amcrest

_ONLINE = "binary_sensor.amcrest_camera_online"
_MOTION = "binary_sensor.amcrest_camera_motion_detected"
_CAMERA_NAME = "Amcrest Camera"
_MOTION_EVENT_CODE = "VideoMotion"

# The event-driven motion sensor, which the shared CAMERA_CONFIG cannot use:
# it is mutually exclusive with the polled variant.
_EVENT_CONFIG = {
    "amcrest": [
        {
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
            "binary_sensors": ["motion_detected"],
        }
    ]
}


@pytest.mark.parametrize(
    ("event_channels", "expected_state"),
    [
        pytest.param([1], STATE_ON, id="motion_detected"),
        pytest.param([], STATE_OFF, id="no_motion"),
    ],
)
@pytest.mark.usefixtures("mock_event_monitor")
async def test_polled_binary_sensor_reflects_event_channels(
    hass: HomeAssistant,
    mock_api: _MockAmcrestAPI,
    event_channels: list[int],
    expected_state: str,
) -> None:
    """The polled motion sensor is on only while the camera reports a fired channel."""
    mock_api.event_channels = event_channels

    await setup_amcrest(hass, mock_api)

    assert hass.states.get(_MOTION).state == expected_state


@pytest.mark.usefixtures("mock_event_monitor")
async def test_online_sensor_stays_available_when_camera_is_not(
    hass: HomeAssistant, mock_api: _MockAmcrestAPI
) -> None:
    """The online sensor keeps reporting during an outage; the others do not."""
    mock_api.available = False

    await setup_amcrest(hass, mock_api)

    # The online sensor is the one entity that must survive an outage - it is
    # what tells the user the camera is down, so it must never go unavailable.
    assert hass.states.get(_ONLINE).state != STATE_UNAVAILABLE
    assert hass.states.get(_MOTION).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_event_monitor")
async def test_polled_binary_sensor_update_error_is_handled(
    hass: HomeAssistant, mock_api: _MockAmcrestAPI
) -> None:
    """An AmcrestError while polling for events does not propagate."""
    mock_api.set_error("event_channels_happened", AmcrestError("timeout"))

    await setup_amcrest(hass, mock_api)

    assert hass.states.get(_MOTION) is not None
    assert hass.states.get(_ONLINE).state == STATE_ON


@pytest.mark.usefixtures("mock_event_monitor")
async def test_event_sensor_updates_from_dispatcher(
    hass: HomeAssistant, mock_api: _MockAmcrestAPI
) -> None:
    """A dispatched camera event flips the event-driven motion sensor."""
    # The shared config uses the polled motion sensor, which never subscribes to
    # events; the event-driven variant is mutually exclusive with it.
    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_api
    ):
        assert await async_setup_component(hass, "amcrest", _EVENT_CONFIG)
        await hass.async_block_till_done()

    assert hass.states.get(_MOTION).state == STATE_OFF

    async_dispatcher_send(
        hass,
        service_signal(SERVICE_EVENT, _CAMERA_NAME, _MOTION_EVENT_CODE),
        True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(_MOTION).state == STATE_ON


@pytest.mark.usefixtures("mock_event_monitor")
async def test_online_sensor_follows_availability_signal(
    hass: HomeAssistant, mock_api: _MockAmcrestAPI
) -> None:
    """The online sensor re-renders when the camera's availability signal fires."""
    await setup_amcrest(hass, mock_api)
    assert hass.states.get(_ONLINE).state == STATE_ON

    mock_api.available = False
    async_dispatcher_send(hass, service_signal(SERVICE_UPDATE, _CAMERA_NAME))
    await hass.async_block_till_done()

    assert hass.states.get(_ONLINE).state == STATE_OFF
