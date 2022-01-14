"""Tradfri cover (recognised as blinds in the IKEA ecosystem) platform tests."""

from copy import deepcopy
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from pytradfri.device import Device
from pytradfri.device.blind import Blind
from pytradfri.device.blind_control import BlindControl

from homeassistant.components import tradfri

from . import GATEWAY_ID

from tests.common import MockConfigEntry

SET_POSITION_TEST_CASES = [
    # Open cover
    [{}, {"position": 100}, {"state": "open"}],
    # Close cover
    [{}, {"position": 0}, {"state": "closed"}],
]


@pytest.fixture(autouse=True, scope="module")
def setup(request):
    """Set up patches for pytradfri methods."""
    p_1 = patch(
        "pytradfri.device.BlindControl.raw",
        new_callable=PropertyMock,
        return_value=[{"mock": "mock"}],
    )
    p_2 = patch("pytradfri.device.BlindControl.blinds")
    p_1.start()
    p_2.start()

    def teardown():
        """Remove patches for pytradfri methods."""
        p_1.stop()
        p_2.stop()

    request.addfinalizer(teardown)


async def setup_integration(hass):
    """Load the Tradfri platform with a mock gateway."""
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            "host": "mock-host",
            "identity": "mock-identity",
            "key": "mock-key",
            "import_groups": True,
            "gateway_id": GATEWAY_ID,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


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


def create_all_set_position_on_cases():
    """Create all test cases."""
    all_test_cases = [
        ["test_features", "test_data", "expected_result", "device_id"],
        [],
    ]
    index = 1
    for test_case in SET_POSITION_TEST_CASES:
        case = deepcopy(test_case)
        case.append(index)
        index += 1
        all_test_cases[1].append(case)

    return all_test_cases


@pytest.mark.parametrize(*create_all_set_position_on_cases())
async def test_set_cover_position(
    hass,
    mock_gateway,
    mock_api_factory,
    test_features,
    test_data,
    expected_result,
    device_id,
):
    """Test setting position of a cover."""
    # Note pytradfri style, not hass. Values not really important.
    initial_state = {
        "current_cover_position": 0,
    }

    # Setup the gateway with a mock cover.
    cover = mock_cover(
        test_features=test_features, test_state=initial_state, device_number=device_id
    )
    mock_gateway.mock_devices.append(cover)
    await setup_integration(hass)

    # Use the turn_on service call to change the cover state.
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": f"cover.tradfri_cover_{device_id}", **test_data},
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
    # State on command data.
    data = {"15015": [{"5536": 50.0}]}
    # Add data for all sent commands.
    for resp in responses:
        data["15015"][0] = {**data["15015"][0], **resp["15015"][0]}

    # Use the callback function to update the cover state.
    dev = Device(data)
    cover_data = Blind(dev, 0)
    cover.blind_control.blinds[0] = cover_data
    callback(cover)
    await hass.async_block_till_done()

    # Check that the state is correct.
    state = hass.states.get(f"cover.tradfri_cover_{device_id}")
    for result, value in expected_result.items():
        assert state.state == value
