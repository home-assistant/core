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
    data={"Temperature": {"values": [{"s": "2"}], "unit": "degrees_celsius"}},
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
    data={"Temperature": {"values": [{"s": "2"}], "unit": "degrees_celsius"}},
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
    data={"SomeUnsupportedField": {"values": [{"s": "2"}], "unit": "degrees_celsius"}},
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
    data={"Temperature": {"values": [{"s": "2.3"}], "unit": "degrees_celsius"}},
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
    data={"WetDry": {"values": [{"s": "dry"}], "unit": "wet_dry"}},
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
    data={"HeatIndex": {"values": [{"s": 2.3}], "unit": "degrees_fahrenheit"}},
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
    data={"WindSpeed": {"values": [{"s": 2}], "unit": "kilometers_per_hour"}},
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
    data={},
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
    data={"Temperature": None},
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
    data={"Temperature": {"values": [{"s": "2.1"}], "unit": "degrees_fahrenheit"}},
    permissions={"read": True},
    model="Test",
)
