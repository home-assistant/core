"""Tests for the LaCrosse View integration."""

from lacrosse_view import Location, Sensor

MOCK_ENTRY_DATA = {
    "username": "test-username",
    "password": "test-password",
    "id": "1",
    "name": "Test",
}
TEST_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["Temperature"],
    location=Location(id="1", name="Test"),
    data={
        "data": {
            "current": {
                "Temperature": {"spot": {"value": "2"}, "unit": "degrees_celsius"}
            }
        }
    },
    permissions={"read": True},
    model="Test",
)
TEST_NO_PERMISSION_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["Temperature"],
    location=Location(id="1", name="Test"),
    data={
        "data": {
            "current": {
                "Temperature": {"spot": {"value": "2"}, "unit": "degrees_celsius"}
            }
        }
    },
    permissions={"read": False},
    model="Test",
)
TEST_UNSUPPORTED_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["SomeUnsupportedField"],
    location=Location(id="1", name="Test"),
    data={
        "data": {
            "current": {
                "SomeUnsupportedField": {
                    "spot": {"value": "2"},
                    "unit": "degrees_celsius",
                }
            }
        }
    },
    permissions={"read": True},
    model="Test",
)
TEST_FLOAT_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["Temperature"],
    location=Location(id="1", name="Test"),
    data={
        "data": {
            "current": {
                "Temperature": {"spot": {"value": "2.3"}, "unit": "degrees_celsius"}
            }
        }
    },
    permissions={"read": True},
    model="Test",
)
TEST_STRING_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["WetDry"],
    location=Location(id="1", name="Test"),
    data={
        "data": {"current": {"WetDry": {"spot": {"value": "dry"}, "unit": "wet_dry"}}}
    },
    permissions={"read": True},
    model="Test",
)
TEST_ALREADY_FLOAT_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["HeatIndex"],
    location=Location(id="1", name="Test"),
    data={
        "data": {
            "current": {
                "HeatIndex": {"spot": {"value": 2.3}, "unit": "degrees_fahrenheit"}
            }
        }
    },
    permissions={"read": True},
    model="Test",
)
TEST_ALREADY_INT_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["WindSpeed"],
    location=Location(id="1", name="Test"),
    data={
        "data": {
            "current": {
                "WindSpeed": {"spot": {"value": 2}, "unit": "kilometers_per_hour"}
            }
        }
    },
    permissions={"read": True},
    model="Test",
)
TEST_NO_FIELD_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["Temperature"],
    location=Location(id="1", name="Test"),
    data={"data": {"current": {}}},
    permissions={"read": True},
    model="Test",
)
TEST_MISSING_FIELD_DATA_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["Temperature"],
    location=Location(id="1", name="Test"),
    data={"data": {"current": {"Temperature": None}}},
    permissions={"read": True},
    model="Test",
)
TEST_UNITS_OVERRIDE_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["Temperature"],
    location=Location(id="1", name="Test"),
    data={
        "data": {
            "current": {
                "Temperature": {"spot": {"value": "2.1"}, "unit": "degrees_fahrenheit"}
            }
        }
    },
    permissions={"read": True},
    model="Test",
)
TEST_NO_READINGS_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["Temperature"],
    location=Location(id="1", name="Test"),
    data={"error": "no_readings"},
    permissions={"read": True},
    model="Test",
)
TEST_OTHER_ERROR_SENSOR = Sensor(
    name="Test",
    device_id="1",
    type="Test",
    sensor_id="2",
    sensor_field_names=["Temperature"],
    location=Location(id="1", name="Test"),
    data={"error": "some_other_error"},
    permissions={"read": True},
    model="Test",
)
