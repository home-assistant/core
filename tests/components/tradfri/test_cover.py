"""Tradfri cover (recognised as blinds in the IKEA ecosystem) platform tests."""

from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from pytradfri.device import Device
from pytradfri.device.blind import Blind
from pytradfri.device.blind_control import BlindControl

from .common import setup_integration


@pytest.fixture(autouse=True, scope="module")
def setup(request):
    """Set up patches for pytradfri methods."""
    with patch(
        "pytradfri.device.BlindControl.raw",
        new_callable=PropertyMock,
        return_value=[{"mock": "mock"}],
    ), patch(
        "pytradfri.device.BlindControl.blinds",
    ):
        yield


def mock_cover(test_features=None, test_state=None, device_number=0):
    """Mock a tradfri cover/blind."""
    if test_features is None:
        test_features = {}
    if test_state is None:
        test_state = {}
    mock_cover_data = Mock(**test_state)

    dev_info_mock = MagicMock()
    dev_info_mock.manufacturer = "manufacturer"
    dev_info_mock.model_number = "model"
    dev_info_mock.firmware_version = "1.2.3"
    _mock_cover = Mock(
        id=f"mock-cover-id-{device_number}",
        reachable=True,
        observe=Mock(),
        device_info=dev_info_mock,
        has_light_control=False,
        has_socket_control=False,
        has_blind_control=True,
        has_signal_repeater_control=False,
        has_air_purifier_control=False,
    )
    _mock_cover.name = f"tradfri_cover_{device_number}"

    # Set supported features for the covers.
    blind_control = BlindControl(_mock_cover)

    # Store the initial state.
    setattr(blind_control, "blinds", [mock_cover_data])
    _mock_cover.blind_control = blind_control
    return _mock_cover


async def test_cover(hass, mock_gateway, mock_api_factory):
    """Test that covers are correctly added."""
    state = {
        "current_cover_position": 40,
    }

    mock_gateway.mock_devices.append(mock_cover(test_state=state))
    await setup_integration(hass)

    cover_1 = hass.states.get("cover.tradfri_cover_0")
    assert cover_1 is not None
    assert cover_1.state == "open"
    assert cover_1.attributes["current_position"] == 60


async def test_cover_observed(hass, mock_gateway, mock_api_factory):
    """Test that covers are correctly observed."""
    state = {
        "current_cover_position": 1,
    }

    cover = mock_cover(test_state=state)
    mock_gateway.mock_devices.append(cover)
    await setup_integration(hass)
    assert len(cover.observe.mock_calls) > 0


async def test_cover_available(hass, mock_gateway, mock_api_factory):
    """Test cover available property."""

    cover = mock_cover(test_state={"current_cover_position": 1}, device_number=1)
    cover.reachable = True

    cover2 = mock_cover(test_state={"current_cover_position": 1}, device_number=2)
    cover2.reachable = False

    mock_gateway.mock_devices.append(cover)
    mock_gateway.mock_devices.append(cover2)
    await setup_integration(hass)

    assert hass.states.get("cover.tradfri_cover_1").state == "open"
    assert hass.states.get("cover.tradfri_cover_2").state == "unavailable"


@pytest.mark.parametrize(
    "test_data, expected_result",
    [({"position": 100}, "open"), ({"position": 0}, "closed")],
)
async def test_set_cover_position(
    hass,
    mock_gateway,
    mock_api_factory,
    test_data,
    expected_result,
):
    """Test setting position of a cover."""
    # Note pytradfri style, not hass. Values not really important.
    initial_state = {
        "current_cover_position": 0,
    }

    # Setup the gateway with a mock cover.
    cover = mock_cover(test_state=initial_state, device_number=0)
    mock_gateway.mock_devices.append(cover)
    await setup_integration(hass)

    # Use the turn_on service call to change the cover state.
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.tradfri_cover_0", **test_data},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Check that the cover is observed.
    mock_func = cover.observe
    assert len(mock_func.mock_calls) > 0
    _, callkwargs = mock_func.call_args
    assert "callback" in callkwargs
    # Callback function to refresh cover state.
    callback = callkwargs["callback"]

    responses = mock_gateway.mock_responses

    # Use the callback function to update the cover state.
    dev = Device(responses[0])
    cover_data = Blind(dev, 0)
    cover.blind_control.blinds[0] = cover_data
    callback(cover)
    await hass.async_block_till_done()

    # Check that the state is correct.
    state = hass.states.get("cover.tradfri_cover_0")
    assert state.state == expected_result
