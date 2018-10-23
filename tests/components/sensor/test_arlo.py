"""The tests for the Netgear Arlo sensors."""
from collections import namedtuple
from unittest.mock import patch, MagicMock
import pytest
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY, ATTR_ATTRIBUTION)
from homeassistant.components.sensor import arlo
from homeassistant.components.arlo import DATA_ARLO


def _get_named_tuple(input_dict):
    return namedtuple('Struct', input_dict.keys())(*input_dict.values())


def _get_sensor(name='Last', sensor_type='last_capture', data=None):
    if data is None:
        data = {}
    return arlo.ArloSensor(name, data, sensor_type)


@pytest.fixture()
def default_sensor():
    """Create an ArloSensor with default values."""
    return _get_sensor()


@pytest.fixture()
def battery_sensor():
    """Create an ArloSensor with battery data."""
    data = _get_named_tuple({
        'battery_level': 50
    })
    return _get_sensor('Battery Level', 'battery_level', data)


@pytest.fixture()
def temperature_sensor():
    """Create a temperature ArloSensor."""
    return _get_sensor('Temperature', 'temperature')


@pytest.fixture()
def humidity_sensor():
    """Create a humidity ArloSensor."""
    return _get_sensor('Humidity', 'humidity')


@pytest.fixture()
def cameras_sensor():
    """Create a total cameras ArloSensor."""
    data = _get_named_tuple({
        'cameras': [0, 0]
    })
    return _get_sensor('Arlo Cameras', 'total_cameras', data)


@pytest.fixture()
def captured_sensor():
    """Create a captured today ArloSensor."""
    data = _get_named_tuple({
        'captured_today': [0, 0, 0, 0, 0]
    })
    return _get_sensor('Captured Today', 'captured_today', data)


class PlatformSetupFixture():
    """Fixture for testing platform setup call to add_entities()."""

    def __init__(self):
        """Instantiate the platform setup fixture."""
        self.sensors = None
        self.update = False

    def add_entities(self, sensors, update):
        """Mock method for adding devices."""
        self.sensors = sensors
        self.update = update


@pytest.fixture()
def platform_setup():
    """Create an instance of the PlatformSetupFixture class."""
    return PlatformSetupFixture()


@pytest.fixture()
def sensor_with_hass_data(default_sensor, hass):
    """Create a sensor with async_dispatcher_connected mocked."""
    hass.data = {}
    default_sensor.hass = hass
    return default_sensor


@pytest.fixture()
def mock_dispatch():
    """Mock the dispatcher connect method."""
    target = 'homeassistant.components.sensor.arlo.async_dispatcher_connect'
    with patch(target, MagicMock()) as _mock:
        yield _mock


def test_setup_with_no_data(platform_setup, hass):
    """Test setup_platform with no data."""
    arlo.setup_platform(hass, None, platform_setup.add_entities)
    assert platform_setup.sensors is None
    assert not platform_setup.update


def test_setup_with_valid_data(platform_setup, hass):
    """Test setup_platform with valid data."""
    config = {
        'monitored_conditions': [
            'last_capture',
            'total_cameras',
            'captured_today',
            'battery_level',
            'signal_strength',
            'temperature',
            'humidity',
            'air_quality'
        ]
    }

    hass.data[DATA_ARLO] = _get_named_tuple({
        'cameras': [_get_named_tuple({
            'name': 'Camera',
            'model_id': 'ABC1000'
        })],
        'base_stations': [_get_named_tuple({
            'name': 'Base Station',
            'model_id': 'ABC1000'
        })]
    })

    arlo.setup_platform(hass, config, platform_setup.add_entities)
    assert len(platform_setup.sensors) == 8
    assert platform_setup.update


def test_sensor_name(default_sensor):
    """Test the name property."""
    assert default_sensor.name == 'Last'


async def test_async_added_to_hass(sensor_with_hass_data, mock_dispatch):
    """Test dispatcher called when added."""
    await sensor_with_hass_data.async_added_to_hass()
    assert len(mock_dispatch.mock_calls) == 1
    kall = mock_dispatch.call_args
    args, kwargs = kall
    assert len(args) == 3
    assert args[0] == sensor_with_hass_data.hass
    assert args[1] == 'arlo_update'
    assert not kwargs


def test_sensor_state_default(default_sensor):
    """Test the state property."""
    assert default_sensor.state is None


def test_sensor_icon_battery(battery_sensor):
    """Test the battery icon."""
    assert battery_sensor.icon == 'mdi:battery-50'


def test_sensor_icon(temperature_sensor):
    """Test the icon property."""
    assert temperature_sensor.icon == 'mdi:thermometer'


def test_unit_of_measure(default_sensor, battery_sensor):
    """Test the unit_of_measurement property."""
    assert default_sensor.unit_of_measurement is None
    assert battery_sensor.unit_of_measurement == '%'


def test_device_class(default_sensor, temperature_sensor, humidity_sensor):
    """Test the device_class property."""
    assert default_sensor.device_class is None
    assert temperature_sensor.device_class == DEVICE_CLASS_TEMPERATURE
    assert humidity_sensor.device_class == DEVICE_CLASS_HUMIDITY


def test_update_total_cameras(cameras_sensor):
    """Test update method for total_cameras sensor type."""
    cameras_sensor.update()
    assert cameras_sensor.state == 2


def test_update_captured_today(captured_sensor):
    """Test update method for captured_today sensor type."""
    captured_sensor.update()
    assert captured_sensor.state == 5


def _test_attributes(sensor_type):
    data = _get_named_tuple({
        'model_id': 'TEST123'
    })
    sensor = _get_sensor('test', sensor_type, data)
    attrs = sensor.device_state_attributes
    assert attrs.get(ATTR_ATTRIBUTION) == 'Data provided by arlo.netgear.com'
    assert attrs.get('brand') == 'Netgear Arlo'
    assert attrs.get('model') == 'TEST123'


def test_state_attributes():
    """Test attributes for camera sensor types."""
    _test_attributes('battery_level')
    _test_attributes('signal_strength')
    _test_attributes('temperature')
    _test_attributes('humidity')
    _test_attributes('air_quality')


def test_attributes_total_cameras(cameras_sensor):
    """Test attributes for total cameras sensor type."""
    attrs = cameras_sensor.device_state_attributes
    assert attrs.get(ATTR_ATTRIBUTION) == 'Data provided by arlo.netgear.com'
    assert attrs.get('brand') == 'Netgear Arlo'
    assert attrs.get('model') is None


def _test_update(sensor_type, key, value):
    data = _get_named_tuple({
        key: value
    })
    sensor = _get_sensor('test', sensor_type, data)
    sensor.update()
    assert sensor.state == value


def test_update():
    """Test update method for direct transcription sensor types."""
    _test_update('battery_level', 'battery_level', 100)
    _test_update('signal_strength', 'signal_strength', 100)
    _test_update('temperature', 'ambient_temperature', 21.4)
    _test_update('humidity', 'ambient_humidity', 45.1)
    _test_update('air_quality', 'ambient_air_quality', 14.2)
