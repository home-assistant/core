"""Tradfri lights platform tests."""

from copy import deepcopy
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from pytradfri.device import Device
from pytradfri.device.light import Light
from pytradfri.device.light_control import LightControl

from homeassistant.components import tradfri

from . import MOCK_GATEWAY_ID

from tests.common import MockConfigEntry

DEFAULT_TEST_FEATURES = {
    "can_set_dimmer": False,
    "can_set_color": False,
    "can_set_temp": False,
}
# [
#     {bulb features},
#     {turn_on arguments},
#     {expected result}
# ]
TURN_ON_TEST_CASES = [
    # Turn On
    [{}, {}, {"state": "on"}],
    # Brightness > 0
    [{"can_set_dimmer": True}, {"brightness": 100}, {"state": "on", "brightness": 100}],
    # Brightness == 1
    [{"can_set_dimmer": True}, {"brightness": 1}, {"brightness": 1}],
    # Brightness > 254
    [{"can_set_dimmer": True}, {"brightness": 1000}, {"brightness": 254}],
    # color_temp
    [{"can_set_temp": True}, {"color_temp": 250}, {"color_temp": 250}],
    # color_temp < 250
    [{"can_set_temp": True}, {"color_temp": 1}, {"color_temp": 250}],
    # color_temp > 454
    [{"can_set_temp": True}, {"color_temp": 1000}, {"color_temp": 454}],
    # hs color
    [
        {"can_set_color": True},
        {"hs_color": [300, 100]},
        {"state": "on", "hs_color": [300, 100]},
    ],
    # ct + brightness
    [
        {"can_set_dimmer": True, "can_set_temp": True},
        {"color_temp": 250, "brightness": 200},
        {"state": "on", "color_temp": 250, "brightness": 200},
    ],
    # ct + brightness (no temp support)
    [
        {"can_set_dimmer": True, "can_set_temp": False, "can_set_color": True},
        {"color_temp": 250, "brightness": 200},
        {"state": "on", "hs_color": [26.807, 34.869], "brightness": 200},
    ],
    # ct + brightness (no temp or color support)
    [
        {"can_set_dimmer": True, "can_set_temp": False, "can_set_color": False},
        {"color_temp": 250, "brightness": 200},
        {"state": "on", "brightness": 200},
    ],
    # hs + brightness
    [
        {"can_set_dimmer": True, "can_set_color": True},
        {"hs_color": [300, 100], "brightness": 200},
        {"state": "on", "hs_color": [300, 100], "brightness": 200},
    ],
]

# Result of transition is not tested, but data is passed to turn on service.
TRANSITION_CASES_FOR_TESTS = [None, 0, 1]


@pytest.fixture(autouse=True, scope="module")
def setup(request):
    """Set up patches for pytradfri methods."""
    p_1 = patch(
        "pytradfri.device.LightControl.raw",
        new_callable=PropertyMock,
        return_value=[{"mock": "mock"}],
    )
    p_2 = patch("pytradfri.device.LightControl.lights")
    p_1.start()
    p_2.start()

    def teardown():
        """Remove patches for pytradfri methods."""
        p_1.stop()
        p_2.stop()

    request.addfinalizer(teardown)


async def generate_psk(self, code):
    """Mock psk."""
    return "mock"


async def setup_integration(hass):
    """Load the Tradfri platform with a mock gateway."""
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            "host": "mock-host",
            "identity": "mock-identity",
            "key": "mock-key",
            "import_groups": True,
            "gateway_id": MOCK_GATEWAY_ID,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def mock_light(test_features=None, test_state=None, light_number=0):
    """Mock a tradfri light."""
    if test_features is None:
        test_features = {}
    if test_state is None:
        test_state = {}
    mock_light_data = Mock(**test_state)

    dev_info_mock = MagicMock()
    dev_info_mock.manufacturer = "manufacturer"
    dev_info_mock.model_number = "model"
    dev_info_mock.firmware_version = "1.2.3"
    _mock_light = Mock(
        id=f"mock-light-id-{light_number}",
        reachable=True,
        observe=Mock(),
        device_info=dev_info_mock,
        has_light_control=True,
        has_socket_control=False,
        has_blind_control=False,
        has_signal_repeater_control=False,
    )
    _mock_light.name = f"tradfri_light_{light_number}"

    # Set supported features for the light.
    features = {**DEFAULT_TEST_FEATURES, **test_features}
    light_control = LightControl(_mock_light)
    for attr, value in features.items():
        setattr(light_control, attr, value)
    # Store the initial state.
    setattr(light_control, "lights", [mock_light_data])
    _mock_light.light_control = light_control
    return _mock_light


async def test_light(hass, mock_gateway, api_factory):
    """Test that lights are correctly added."""
    features = {"can_set_dimmer": True, "can_set_color": True, "can_set_temp": True}

    state = {
        "state": True,
        "dimmer": 100,
        "color_temp": 250,
        "hsb_xy_color": (100, 100, 100, 100, 100),
    }

    mock_gateway.mock_devices.append(
        mock_light(test_features=features, test_state=state)
    )
    await setup_integration(hass)

    lamp_1 = hass.states.get("light.tradfri_light_0")
    assert lamp_1 is not None
    assert lamp_1.state == "on"
    assert lamp_1.attributes["brightness"] == 100
    assert lamp_1.attributes["hs_color"] == (0.549, 0.153)


async def test_light_observed(hass, mock_gateway, api_factory):
    """Test that lights are correctly observed."""
    light = mock_light()
    mock_gateway.mock_devices.append(light)
    await setup_integration(hass)
    assert len(light.observe.mock_calls) > 0


async def test_light_available(hass, mock_gateway, api_factory):
    """Test light available property."""
    light = mock_light({"state": True}, light_number=1)
    light.reachable = True

    light2 = mock_light({"state": True}, light_number=2)
    light2.reachable = False

    mock_gateway.mock_devices.append(light)
    mock_gateway.mock_devices.append(light2)
    await setup_integration(hass)

    assert hass.states.get("light.tradfri_light_1").state == "on"

    assert hass.states.get("light.tradfri_light_2").state == "unavailable"


def create_all_turn_on_cases():
    """Create all turn on test cases."""
    # Combine TURN_ON_TEST_CASES and TRANSITION_CASES_FOR_TESTS
    all_turn_on_test_cases = [
        ["test_features", "test_data", "expected_result", "device_id"],
        [],
    ]
    index = 1
    for test_case in TURN_ON_TEST_CASES:
        for trans in TRANSITION_CASES_FOR_TESTS:
            case = deepcopy(test_case)
            if trans is not None:
                case[1]["transition"] = trans
            case.append(index)
            index += 1
            all_turn_on_test_cases[1].append(case)

    return all_turn_on_test_cases


@pytest.mark.parametrize(*create_all_turn_on_cases())
async def test_turn_on(
    hass,
    mock_gateway,
    api_factory,
    test_features,
    test_data,
    expected_result,
    device_id,
):
    """Test turning on a light."""
    # Note pytradfri style, not hass. Values not really important.
    initial_state = {
        "state": False,
        "dimmer": 0,
        "color_temp": 250,
        "hsb_xy_color": (100, 100, 100, 100, 100),
    }

    # Setup the gateway with a mock light.
    light = mock_light(
        test_features=test_features, test_state=initial_state, light_number=device_id
    )
    mock_gateway.mock_devices.append(light)
    await setup_integration(hass)

    # Use the turn_on service call to change the light state.
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": f"light.tradfri_light_{device_id}", **test_data},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Check that the light is observed.
    mock_func = light.observe
    assert len(mock_func.mock_calls) > 0
    _, callkwargs = mock_func.call_args
    assert "callback" in callkwargs
    # Callback function to refresh light state.
    callback = callkwargs["callback"]

    responses = mock_gateway.mock_responses
    # State on command data.
    data = {"3311": [{"5850": 1}]}
    # Add data for all sent commands.
    for resp in responses:
        data["3311"][0] = {**data["3311"][0], **resp["3311"][0]}

    # Use the callback function to update the light state.
    dev = Device(data)
    light_data = Light(dev, 0)
    light.light_control.lights[0] = light_data
    callback(light)
    await hass.async_block_till_done()

    # Check that the state is correct.
    states = hass.states.get(f"light.tradfri_light_{device_id}")
    for result, value in expected_result.items():
        if result == "state":
            assert states.state == value
        else:
            # Allow some rounding error in color conversions.
            assert states.attributes[result] == pytest.approx(value, abs=0.01)


async def test_turn_off(hass, mock_gateway, api_factory):
    """Test turning off a light."""
    state = {"state": True, "dimmer": 100}

    light = mock_light(test_state=state)
    mock_gateway.mock_devices.append(light)
    await setup_integration(hass)

    # Use the turn_off service call to change the light state.
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.tradfri_light_0"}, blocking=True
    )
    await hass.async_block_till_done()

    # Check that the light is observed.
    mock_func = light.observe
    assert len(mock_func.mock_calls) > 0
    _, callkwargs = mock_func.call_args
    assert "callback" in callkwargs
    # Callback function to refresh light state.
    callback = callkwargs["callback"]

    responses = mock_gateway.mock_responses
    data = {"3311": [{}]}
    # Add data for all sent commands.
    for resp in responses:
        data["3311"][0] = {**data["3311"][0], **resp["3311"][0]}

    # Use the callback function to update the light state.
    dev = Device(data)
    light_data = Light(dev, 0)
    light.light_control.lights[0] = light_data
    callback(light)
    await hass.async_block_till_done()

    # Check that the state is correct.
    states = hass.states.get("light.tradfri_light_0")
    assert states.state == "off"


def mock_group(test_state=None, group_number=0):
    """Mock a Tradfri group."""
    if test_state is None:
        test_state = {}
    default_state = {"state": False, "dimmer": 0}

    state = {**default_state, **test_state}

    _mock_group = Mock(member_ids=[], observe=Mock(), **state)
    _mock_group.name = f"tradfri_group_{group_number}"
    return _mock_group


async def test_group(hass, mock_gateway, api_factory):
    """Test that groups are correctly added."""
    mock_gateway.mock_groups.append(mock_group())
    state = {"state": True, "dimmer": 100}
    mock_gateway.mock_groups.append(mock_group(state, 1))
    await setup_integration(hass)

    group = hass.states.get("light.tradfri_group_0")
    assert group is not None
    assert group.state == "off"

    group = hass.states.get("light.tradfri_group_1")
    assert group is not None
    assert group.state == "on"
    assert group.attributes["brightness"] == 100


async def test_group_turn_on(hass, mock_gateway, api_factory):
    """Test turning on a group."""
    group = mock_group()
    group2 = mock_group(group_number=1)
    group3 = mock_group(group_number=2)
    mock_gateway.mock_groups.append(group)
    mock_gateway.mock_groups.append(group2)
    mock_gateway.mock_groups.append(group3)
    await setup_integration(hass)

    # Use the turn_off service call to change the light state.
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.tradfri_group_0"}, blocking=True
    )
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.tradfri_group_1", "brightness": 100},
        blocking=True,
    )
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.tradfri_group_2", "brightness": 100, "transition": 1},
        blocking=True,
    )
    await hass.async_block_till_done()

    group.set_state.assert_called_with(1)
    group2.set_dimmer.assert_called_with(100)
    group3.set_dimmer.assert_called_with(100, transition_time=10)


async def test_group_turn_off(hass, mock_gateway, api_factory):
    """Test turning off a group."""
    group = mock_group({"state": True})
    mock_gateway.mock_groups.append(group)
    await setup_integration(hass)

    # Use the turn_off service call to change the light state.
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.tradfri_group_0"}, blocking=True
    )
    await hass.async_block_till_done()

    group.set_state.assert_called_with(0)
