"""Test for RFlink sensor components.

Test setup of rflink sensor component/platform. Verify manual and
automatic sensor creation.

"""

import pytest

from homeassistant.components.rflink import (
    CONF_RECONNECT_INTERVAL,
    DATA_ENTITY_LOOKUP,
    EVENT_KEY_COMMAND,
    EVENT_KEY_SENSOR,
    TMP_ENTITY,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfPrecipitationDepth,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from .test_init import mock_rflink

DOMAIN = "sensor"

CONFIG = {
    "rflink": {
        "port": "/dev/ttyABC0",
        "ignore_devices": ["ignore_wildcard_*", "ignore_sensor"],
    },
    DOMAIN: {
        "platform": "rflink",
        "devices": {"test": {"name": "test", "sensor_type": "temperature"}},
    },
}


async def test_default_setup(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test all basic functionality of the rflink sensor component."""
    # setup mocking rflink module
    event_callback, create, _, _ = await mock_rflink(hass, CONFIG, DOMAIN, monkeypatch)

    # make sure arguments are passed
    assert create.call_args_list[0][1]["ignore"]

    # test default state of sensor loaded from config
    config_sensor = hass.states.get("sensor.test")
    assert config_sensor
    assert config_sensor.state == "unknown"
    assert (
        config_sensor.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    )

    # test event for config sensor
    event_callback(
        {
            "id": "test",
            "sensor": "temperature",
            "value": 1,
            "unit": UnitOfTemperature.CELSIUS,
        }
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test").state == "1"

    # test event for new unconfigured sensor
    event_callback(
        {
            "id": "test2",
            "sensor": "temperature",
            "value": 0,
            "unit": UnitOfTemperature.CELSIUS,
        }
    )
    await hass.async_block_till_done()

    # test state of temp sensor
    temp_sensor = hass.states.get("sensor.test2")
    assert temp_sensor
    assert temp_sensor.state == "0"
    assert temp_sensor.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert (
        ATTR_ICON not in temp_sensor.attributes
    )  # temperature uses SensorEntityDescription

    # test event for new unconfigured sensor
    event_callback({"id": "test3", "sensor": "battery", "value": "ok", "unit": None})
    await hass.async_block_till_done()

    # test state of battery sensor
    bat_sensor = hass.states.get("sensor.test3")
    assert bat_sensor
    assert bat_sensor.state == "ok"
    assert ATTR_UNIT_OF_MEASUREMENT not in bat_sensor.attributes
    assert bat_sensor.attributes[ATTR_ICON] == "mdi:battery"


async def test_disable_automatic_add(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If disabled new devices should not be automatically added."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {"platform": "rflink", "automatic_add": False},
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # test event for new unconfigured sensor
    event_callback(
        {
            "id": "test2",
            "sensor": "temperature",
            "value": 0,
            "unit": UnitOfTemperature.CELSIUS,
        }
    )
    await hass.async_block_till_done()

    # make sure new device is not added
    assert not hass.states.get("sensor.test2")


async def test_entity_availability(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If Rflink device is disconnected, entities should become unavailable."""
    # Make sure Rflink mock does not 'recover' to quickly from the
    # disconnect or else the unavailability cannot be measured
    config = CONFIG
    failures = [True, True]
    config[CONF_RECONNECT_INTERVAL] = 60

    # Create platform and entities
    _, _, _, disconnect_callback = await mock_rflink(
        hass, config, DOMAIN, monkeypatch, failures=failures
    )

    # Entities are available by default
    assert hass.states.get("sensor.test").state == STATE_UNKNOWN

    # Mock a disconnect of the Rflink device
    disconnect_callback()

    # Wait for dispatch events to propagate
    await hass.async_block_till_done()

    # Entity should be unavailable
    assert hass.states.get("sensor.test").state == "unavailable"

    # Reconnect the Rflink device
    disconnect_callback()

    # Wait for dispatch events to propagate
    await hass.async_block_till_done()

    # Entities should be available again
    assert hass.states.get("sensor.test").state == STATE_UNKNOWN


async def test_aliases(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate the response to sensor's alias (with aliases)."""
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "test_02": {
                    "name": "test_02",
                    "sensor_type": "humidity",
                    "aliases": ["test_alias_02_0"],
                }
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # test default state of sensor loaded from config
    config_sensor = hass.states.get("sensor.test_02")
    assert config_sensor
    assert config_sensor.state == "unknown"

    # test event for config sensor
    event_callback(
        {
            "id": "test_alias_02_0",
            "sensor": "humidity",
            "value": 65,
            "unit": PERCENTAGE,
        }
    )
    await hass.async_block_till_done()

    # test state of new sensor
    updated_sensor = hass.states.get("sensor.test_02")
    assert updated_sensor
    assert updated_sensor.state == "65"
    assert updated_sensor.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE


async def test_race_condition(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test race condition for unknown components."""
    config = {"rflink": {"port": "/dev/ttyABC0"}, DOMAIN: {"platform": "rflink"}}
    tmp_entity = TMP_ENTITY.format("test3")

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # test event for new unconfigured sensor
    event_callback({"id": "test3", "sensor": "battery", "value": "ok", "unit": ""})
    event_callback({"id": "test3", "sensor": "battery", "value": "ko", "unit": ""})

    # tmp_entity added to EVENT_KEY_SENSOR
    assert tmp_entity in hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_SENSOR]["test3"]
    # tmp_entity must no be added to EVENT_KEY_COMMAND
    assert tmp_entity not in hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_COMMAND]["test3"]

    await hass.async_block_till_done()

    # test state of new sensor
    updated_sensor = hass.states.get("sensor.test3")
    assert updated_sensor

    # test state of new sensor
    new_sensor = hass.states.get(f"{DOMAIN}.test3")
    assert new_sensor
    assert new_sensor.state == "ok"

    event_callback({"id": "test3", "sensor": "battery", "value": "ko", "unit": ""})
    await hass.async_block_till_done()
    # tmp_entity must be deleted from EVENT_KEY_COMMAND
    assert tmp_entity not in hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_SENSOR]["test3"]

    # test state of new sensor
    new_sensor = hass.states.get(f"{DOMAIN}.test3")
    assert new_sensor
    assert new_sensor.state == "ko"


async def test_sensor_attributes(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate the sensor attributes."""

    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "my_meter_device_unique_id": {
                    "name": "meter_device",
                    "sensor_type": "meter_value",
                },
                "my_rain_device_unique_id": {
                    "name": "rain_device",
                    "sensor_type": "total_rain",
                },
                "my_humidity_device_unique_id": {
                    "name": "humidity_device",
                    "sensor_type": "humidity",
                },
                "my_temperature_device_unique_id": {
                    "name": "temperature_device",
                    "sensor_type": "temperature",
                },
                "another_temperature_device_unique_id": {
                    "name": "fahrenheit_device",
                    "sensor_type": "temperature",
                    "unit_of_measurement": "F",
                },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    # test sensor loaded from config
    meter_state = hass.states.get("sensor.meter_device")
    assert meter_state
    assert "device_class" not in meter_state.attributes
    assert "state_class" not in meter_state.attributes
    assert "unit_of_measurement" not in meter_state.attributes

    rain_state = hass.states.get("sensor.rain_device")
    assert rain_state
    assert rain_state.attributes["device_class"] == SensorDeviceClass.PRECIPITATION
    assert rain_state.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING
    assert (
        rain_state.attributes["unit_of_measurement"]
        == UnitOfPrecipitationDepth.MILLIMETERS
    )

    humidity_state = hass.states.get("sensor.humidity_device")
    assert humidity_state
    assert humidity_state.attributes["device_class"] == SensorDeviceClass.HUMIDITY
    assert humidity_state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert humidity_state.attributes["unit_of_measurement"] == PERCENTAGE

    temperature_state = hass.states.get("sensor.temperature_device")
    assert temperature_state
    assert temperature_state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert temperature_state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert (
        temperature_state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    )

    fahrenheit_state = hass.states.get("sensor.fahrenheit_device")
    assert fahrenheit_state
    assert fahrenheit_state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert fahrenheit_state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert fahrenheit_state.attributes["unit_of_measurement"] == "F"
