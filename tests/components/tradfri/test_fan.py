"""Tradfri fan (recognised as air purifiers in the IKEA ecosystem) platform tests."""

from unittest.mock import MagicMock, Mock

import pytest
from pytradfri.device import Device
from pytradfri.device.air_purifier import AirPurifier
from pytradfri.device.air_purifier_control import AirPurifierControl

from .common import setup_integration


def mock_fan(test_features=None, test_state=None, device_number=0):
    """Mock a tradfri fan/air purifier."""
    if test_features is None:
        test_features = {}
    if test_state is None:
        test_state = {}
    mock_fan_data = Mock(**test_state)

    dev_info_mock = MagicMock()
    dev_info_mock.manufacturer = "manufacturer"
    dev_info_mock.model_number = "model"
    dev_info_mock.firmware_version = "1.2.3"
    _mock_fan = Mock(
        id=f"mock-fan-id-{device_number}",
        reachable=True,
        observe=Mock(),
        device_info=dev_info_mock,
        has_light_control=False,
        has_socket_control=False,
        has_blind_control=False,
        has_signal_repeater_control=False,
        has_air_purifier_control=True,
    )
    _mock_fan.name = f"tradfri_fan_{device_number}"
    air_purifier_control = AirPurifierControl(_mock_fan)

    # Store the initial state.
    setattr(air_purifier_control, "air_purifiers", [mock_fan_data])
    _mock_fan.air_purifier_control = air_purifier_control
    return _mock_fan


async def test_fan(hass, mock_gateway, mock_api_factory):
    """Test that fans are correctly added."""
    state = {"fan_speed": 10, "air_quality": 12}

    mock_gateway.mock_devices.append(mock_fan(test_state=state))
    await setup_integration(hass)

    fan_1 = hass.states.get("fan.tradfri_fan_0")
    assert fan_1 is not None
    assert fan_1.state == "on"
    assert fan_1.attributes["percentage"] == 18
    assert fan_1.attributes["preset_modes"] == ["Auto"]
    assert fan_1.attributes["supported_features"] == 9


async def test_fan_observed(hass, mock_gateway, mock_api_factory):
    """Test that fans are correctly observed."""
    state = {"fan_speed": 10, "air_quality": 12}

    fan = mock_fan(test_state=state)
    mock_gateway.mock_devices.append(fan)
    await setup_integration(hass)
    assert len(fan.observe.mock_calls) > 0


async def test_fan_available(hass, mock_gateway, mock_api_factory):
    """Test fan available property."""

    fan = mock_fan(test_state={"fan_speed": 10, "air_quality": 12}, device_number=1)
    fan.reachable = True

    fan2 = mock_fan(test_state={"fan_speed": 10, "air_quality": 12}, device_number=2)
    fan2.reachable = False

    mock_gateway.mock_devices.append(fan)
    mock_gateway.mock_devices.append(fan2)
    await setup_integration(hass)

    assert hass.states.get("fan.tradfri_fan_1").state == "on"
    assert hass.states.get("fan.tradfri_fan_2").state == "unavailable"


@pytest.mark.parametrize(
    "test_data, expected_result",
    [
        (
            {"percentage": 50},
            "on",
        ),
        ({"percentage": 0}, "off"),
    ],
)
async def test_set_percentage(
    hass,
    mock_gateway,
    mock_api_factory,
    test_data,
    expected_result,
):
    """Test setting speed of a fan."""
    # Note pytradfri style, not hass. Values not really important.
    initial_state = {"percentage": 10, "fan_speed": 3, "air_quality": 12}
    # Setup the gateway with a mock fan.
    fan = mock_fan(test_state=initial_state, device_number=0)
    mock_gateway.mock_devices.append(fan)
    await setup_integration(hass)

    # Use the turn_on service call to change the fan state.
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": "fan.tradfri_fan_0", **test_data},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Check that the fan is observed.
    mock_func = fan.observe
    assert len(mock_func.mock_calls) > 0
    _, callkwargs = mock_func.call_args
    assert "callback" in callkwargs
    # Callback function to refresh fan state.
    callback = callkwargs["callback"]

    responses = mock_gateway.mock_responses
    mock_gateway_response = responses[0]

    # A KeyError is raised if we don't this to the response code
    mock_gateway_response["15025"][0].update({"5908": 10, "5907": 12, "5910": 20})

    # Use the callback function to update the fan state.
    dev = Device(mock_gateway_response)
    fan_data = AirPurifier(dev, 0)
    fan.air_purifier_control.air_purifiers[0] = fan_data
    callback(fan)
    await hass.async_block_till_done()

    # Check that the state is correct.
    state = hass.states.get("fan.tradfri_fan_0")
    assert state.state == expected_result
