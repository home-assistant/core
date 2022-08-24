"""Inels sensor platform testing."""
from homeassistant.core import HomeAssistant

from .conftest import setup_inels_test_integration

UNIQUE_ID = "76695425"

CONNECTED_TOPIC = f"inels/connected/7777888/10/{UNIQUE_ID}"
STATUS_TOPIC = f"inels/status/7777888/10/{UNIQUE_ID}"

BATTERY = "battery"
TEMP_OUT = "temperature_out"
TEMP_IN = "temperature_in"
SENSOR_TYPES = [BATTERY, TEMP_IN, TEMP_OUT]

INELS_DATA = b"00\n14\n0A\n1E\n0A\n"
TEMP_IN_VALUE = "25.8"
TEMP_OUT_VALUE = "25.9"

CONNECTED_INELS_VALUE = b"on\n"
DISCONNECTED_INELS_VALUE = b"off\n"


def set_mock_mqtt(mqtt, available):
    """Set mock mqtt communication."""
    mqtt.mock_messages[CONNECTED_TOPIC] = available
    mqtt.mock_messages[STATUS_TOPIC] = INELS_DATA
    mqtt.mock_discovery_all[STATUS_TOPIC] = INELS_DATA


def get_sensors(hass: HomeAssistant, unique_id):
    """Return instance of the sensor."""
    sensors = {}
    for s_type in SENSOR_TYPES:
        sensors[s_type] = hass.states.get(f"sensor.{unique_id}_{s_type}")

    return sensors


async def test_sensor_not_available(hass: HomeAssistant, mock_mqtt):
    """Test sensor availability."""
    set_mock_mqtt(mock_mqtt, DISCONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    sensors = get_sensors(hass, UNIQUE_ID)

    for sensor in sensors.items():
        assert sensor[1].state == "unavailable"


async def test_sensor_available(hass: HomeAssistant, mock_mqtt):
    """Test sensor availability."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    sensors = get_sensors(hass, UNIQUE_ID)

    for sensor in sensors.items():
        assert sensor[1].state != "unavailable"


async def test_sensor_battery_level(hass: HomeAssistant, mock_mqtt):
    """Test sensors battery level."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    sensors = get_sensors(hass, UNIQUE_ID)
    battery_sensor = sensors[BATTERY]

    assert battery_sensor is not None
    assert battery_sensor.attributes["device_class"] == BATTERY
    assert battery_sensor.attributes["unit_of_measurement"] == "%"


async def test_sensor_temperatures(hass: HomeAssistant, mock_mqtt):
    """Test sensor temperature."""
    set_mock_mqtt(mock_mqtt, CONNECTED_INELS_VALUE)
    await setup_inels_test_integration(hass)

    sensors = get_sensors(hass, UNIQUE_ID)

    temp_out_sensor = sensors[TEMP_OUT]
    assert temp_out_sensor is not None
    assert temp_out_sensor.attributes["device_class"] == "temperature"
    assert temp_out_sensor.attributes["unit_of_measurement"] == "°C"
    assert temp_out_sensor.state == TEMP_OUT_VALUE

    temp_in_sensor = sensors[TEMP_IN]
    assert temp_in_sensor is not None
    assert temp_in_sensor.attributes["device_class"] == "temperature"
    assert temp_in_sensor.attributes["unit_of_measurement"] == "°C"
    assert temp_in_sensor.state == TEMP_IN_VALUE
