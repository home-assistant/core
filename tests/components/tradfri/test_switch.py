"""Tradfri switch (recognised as sockets in the IKEA ecosystem) platform tests."""

from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from pytradfri.device import Device
from pytradfri.device.socket import Socket
from pytradfri.device.socket_control import SocketControl

from .common import setup_integration


@pytest.fixture(autouse=True, scope="module")
def setup(request):
    """Set up patches for pytradfri methods."""
    with patch(
        "pytradfri.device.SocketControl.raw",
        new_callable=PropertyMock,
        return_value=[{"mock": "mock"}],
    ), patch(
        "pytradfri.device.SocketControl.sockets",
    ):
        yield


def mock_switch(test_features=None, test_state=None, device_number=0):
    """Mock a tradfri switch/socket."""
    if test_features is None:
        test_features = {}
    if test_state is None:
        test_state = {}
    mock_switch_data = Mock(**test_state)

    dev_info_mock = MagicMock()
    dev_info_mock.manufacturer = "manufacturer"
    dev_info_mock.model_number = "model"
    dev_info_mock.firmware_version = "1.2.3"
    _mock_switch = Mock(
        id=f"mock-switch-id-{device_number}",
        reachable=True,
        observe=Mock(),
        device_info=dev_info_mock,
        has_light_control=False,
        has_socket_control=True,
        has_blind_control=False,
        has_signal_repeater_control=False,
        has_air_purifier_control=False,
    )
    _mock_switch.name = f"tradfri_switch_{device_number}"
    socket_control = SocketControl(_mock_switch)

    # Store the initial state.
    setattr(socket_control, "sockets", [mock_switch_data])
    _mock_switch.socket_control = socket_control
    return _mock_switch


async def test_switch(hass, mock_gateway, mock_api_factory):
    """Test that switches are correctly added."""
    state = {
        "state": True,
    }

    mock_gateway.mock_devices.append(mock_switch(test_state=state))
    await setup_integration(hass)

    switch_1 = hass.states.get("switch.tradfri_switch_0")
    assert switch_1 is not None
    assert switch_1.state == "on"


async def test_switch_observed(hass, mock_gateway, mock_api_factory):
    """Test that switches are correctly observed."""
    state = {
        "state": True,
    }

    switch = mock_switch(test_state=state)
    mock_gateway.mock_devices.append(switch)
    await setup_integration(hass)
    assert len(switch.observe.mock_calls) > 0


async def test_switch_available(hass, mock_gateway, mock_api_factory):
    """Test switch available property."""

    switch = mock_switch(test_state={"state": True}, device_number=1)
    switch.reachable = True

    switch2 = mock_switch(test_state={"state": True}, device_number=2)
    switch2.reachable = False

    mock_gateway.mock_devices.append(switch)
    mock_gateway.mock_devices.append(switch2)
    await setup_integration(hass)

    assert hass.states.get("switch.tradfri_switch_1").state == "on"
    assert hass.states.get("switch.tradfri_switch_2").state == "unavailable"


@pytest.mark.parametrize(
    "test_data, expected_result",
    [
        (
            "turn_on",
            "on",
        ),
        ("turn_off", "off"),
    ],
)
async def test_turn_on_off(
    hass,
    mock_gateway,
    mock_api_factory,
    test_data,
    expected_result,
):
    """Test turning switch on/off."""
    # Note pytradfri style, not hass. Values not really important.
    initial_state = {
        "state": True,
    }

    # Setup the gateway with a mock switch.
    switch = mock_switch(test_state=initial_state, device_number=0)
    mock_gateway.mock_devices.append(switch)
    await setup_integration(hass)

    # Use the turn_on/turn_off service call to change the switch state.
    await hass.services.async_call(
        "switch",
        test_data,
        {
            "entity_id": "switch.tradfri_switch_0",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Check that the switch is observed.
    mock_func = switch.observe
    assert len(mock_func.mock_calls) > 0
    _, callkwargs = mock_func.call_args
    assert "callback" in callkwargs
    # Callback function to refresh switch state.
    callback = callkwargs["callback"]

    responses = mock_gateway.mock_responses
    mock_gateway_response = responses[0]

    # Use the callback function to update the switch state.
    dev = Device(mock_gateway_response)
    switch_data = Socket(dev, 0)
    switch.socket_control.sockets[0] = switch_data
    callback(switch)
    await hass.async_block_till_done()

    # Check that the state is correct.
    state = hass.states.get("switch.tradfri_switch_0")
    assert state.state == expected_result
