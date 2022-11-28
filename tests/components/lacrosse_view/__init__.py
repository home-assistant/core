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
