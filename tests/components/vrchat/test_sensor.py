"""Test VRChat sensors."""

from types import SimpleNamespace

from homeassistant.components.vrchat.sensor import VRChatUserLocationSensor


def test_location_sensor_without_world_metadata() -> None:
    """Test an unresolved world ID has no location state."""
    sensor = VRChatUserLocationSensor(
        SimpleNamespace(
            data={"location": "wrld_test", "worldId": "wrld_test"},
            world=None,
            destination_world=None,
        )
    )

    assert sensor.native_value is None
