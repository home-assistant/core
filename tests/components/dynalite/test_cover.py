"""Test Dynalite cover."""
from dynalite_devices_lib.cover import DynaliteTimeCoverWithTiltDevice
import pytest

from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME
from homeassistant.exceptions import HomeAssistantError

from .common import (
    ATTR_ARGS,
    ATTR_METHOD,
    ATTR_SERVICE,
    create_entity_from_device,
    create_mock_device,
    run_service_tests,
)


@pytest.fixture
def mock_device():
    """Mock a Dynalite device."""
    mock_dev = create_mock_device("cover", DynaliteTimeCoverWithTiltDevice)
    mock_dev.device_class = "blind"
    return mock_dev


async def test_cover_setup(hass, mock_device):
    """Test a successful setup."""
    await create_entity_from_device(hass, mock_device)
    entity_state = hass.states.get("cover.name")
    assert entity_state.attributes[ATTR_FRIENDLY_NAME] == mock_device.name
    assert (
        entity_state.attributes["current_position"]
        == mock_device.current_cover_position
    )
    assert (
        entity_state.attributes["current_tilt_position"]
        == mock_device.current_cover_tilt_position
    )
    assert entity_state.attributes[ATTR_DEVICE_CLASS] == mock_device.device_class
    await run_service_tests(
        hass,
        mock_device,
        "cover",
        [
            {ATTR_SERVICE: "open_cover", ATTR_METHOD: "async_open_cover"},
            {ATTR_SERVICE: "close_cover", ATTR_METHOD: "async_close_cover"},
            {ATTR_SERVICE: "stop_cover", ATTR_METHOD: "async_stop_cover"},
            {
                ATTR_SERVICE: "set_cover_position",
                ATTR_METHOD: "async_set_cover_position",
                ATTR_ARGS: {"position": 50},
            },
            {ATTR_SERVICE: "open_cover_tilt", ATTR_METHOD: "async_open_cover_tilt"},
            {ATTR_SERVICE: "close_cover_tilt", ATTR_METHOD: "async_close_cover_tilt"},
            {ATTR_SERVICE: "stop_cover_tilt", ATTR_METHOD: "async_stop_cover_tilt"},
            {
                ATTR_SERVICE: "set_cover_tilt_position",
                ATTR_METHOD: "async_set_cover_tilt_position",
                ATTR_ARGS: {"tilt_position": 50},
            },
        ],
    )


async def test_cover_without_tilt(hass, mock_device):
    """Test a cover with no tilt."""
    mock_device.has_tilt = False
    await create_entity_from_device(hass, mock_device)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "cover", "open_cover_tilt", {"entity_id": "cover.name"}, blocking=True
        )
    await hass.async_block_till_done()
    mock_device.async_open_cover_tilt.assert_not_called()


async def check_cover_position(
    hass, update_func, device, closing, opening, closed, expected
):
    """Check that a given position behaves correctly."""
    device.is_closing = closing
    device.is_opening = opening
    device.is_closed = closed
    update_func(device)
    await hass.async_block_till_done()
    entity_state = hass.states.get("cover.name")
    assert entity_state.state == expected


async def test_cover_positions(hass, mock_device):
    """Test that the state updates in the various positions."""
    update_func = await create_entity_from_device(hass, mock_device)
    await check_cover_position(
        hass, update_func, mock_device, True, False, False, "closing"
    )
    await check_cover_position(
        hass, update_func, mock_device, False, True, False, "opening"
    )
    await check_cover_position(
        hass, update_func, mock_device, False, False, True, "closed"
    )
    await check_cover_position(
        hass, update_func, mock_device, False, False, False, "open"
    )
