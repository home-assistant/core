"""Tests for waterkotte sensors."""
from homeassistant.components.waterkotte_heatpump.sensor import SENSOR_DESCRIPTIONS


def test_sensor_descriptions_have_names() -> None:
    """Ensure all sensor descriptions include a name."""
    for _, description in SENSOR_DESCRIPTIONS.items():
        assert description.name
        assert description.name[0].isupper()
