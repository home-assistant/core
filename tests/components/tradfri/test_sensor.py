"""Tradfri sensor platform tests."""

from unittest.mock import MagicMock, Mock

from .common import setup_integration


def mock_sensor(state_name: str, state_value: str, device_number=0):
    """Mock a tradfri sensor."""
    dev_info_mock = MagicMock()
    dev_info_mock.manufacturer = "manufacturer"
    dev_info_mock.model_number = "model"
    dev_info_mock.firmware_version = "1.2.3"

    # Set state value, eg battery_level = 50
    setattr(dev_info_mock, state_name, state_value)

    _mock_sensor = Mock(
        id=f"mock-sensor-id-{device_number}",
        reachable=True,
        observe=Mock(),
        device_info=dev_info_mock,
        has_light_control=False,
        has_socket_control=False,
        has_blind_control=False,
        has_signal_repeater_control=False,
        has_air_purifier_control=False,
    )
    _mock_sensor.name = f"tradfri_sensor_{device_number}"

    return _mock_sensor


async def test_battery_sensor(hass, mock_gateway, mock_api_factory):
    """Test that a battery sensor is correctly added."""
    mock_gateway.mock_devices.append(
        mock_sensor(state_name="battery_level", state_value=60)
    )
    await setup_integration(hass)

    sensor_1 = hass.states.get("sensor.tradfri_sensor_0")
    assert sensor_1 is not None
    assert sensor_1.state == "60"
    assert sensor_1.attributes["unit_of_measurement"] == "%"
    assert sensor_1.attributes["device_class"] == "battery"


async def test_sensor_observed(hass, mock_gateway, mock_api_factory):
    """Test that sensors are correctly observed."""

    sensor = mock_sensor(state_name="battery_level", state_value=60)
    mock_gateway.mock_devices.append(sensor)
    await setup_integration(hass)
    assert len(sensor.observe.mock_calls) > 0


async def test_sensor_available(hass, mock_gateway, mock_api_factory):
    """Test sensor available property."""

    sensor = mock_sensor(state_name="battery_level", state_value=60, device_number=1)
    sensor.reachable = True

    sensor2 = mock_sensor(state_name="battery_level", state_value=60, device_number=2)
    sensor2.reachable = False

    mock_gateway.mock_devices.append(sensor)
    mock_gateway.mock_devices.append(sensor2)
    await setup_integration(hass)

    assert hass.states.get("sensor.tradfri_sensor_1").state == "60"
    assert hass.states.get("sensor.tradfri_sensor_2").state == "unavailable"
