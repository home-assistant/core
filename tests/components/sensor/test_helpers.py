"""The test for sensor helpers."""
import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor.helpers import async_parse_date_datetime


def test_async_parse_datetime(caplog: pytest.LogCaptureFixture) -> None:
    """Test async_parse_date_datetime."""
    entity_id = "sensor.timestamp"
    device_class = SensorDeviceClass.TIMESTAMP
    assert (
        async_parse_date_datetime(
            "2021-12-12 12:12Z", entity_id, device_class
        ).isoformat()
        == "2021-12-12T12:12:00+00:00"
    )
    assert not caplog.text

    # No timezone
    assert (
        async_parse_date_datetime("2021-12-12 12:12", entity_id, device_class) is None
    )
    assert "sensor.timestamp rendered timestamp without timezone" in caplog.text

    # Invalid timestamp
    assert async_parse_date_datetime("12 past 12", entity_id, device_class) is None
    assert "sensor.timestamp rendered invalid timestamp: 12 past 12" in caplog.text

    device_class = SensorDeviceClass.DATE
    caplog.clear()
    assert (
        async_parse_date_datetime("2021-12-12", entity_id, device_class).isoformat()
        == "2021-12-12"
    )
    assert not caplog.text

    # Invalid date
    assert async_parse_date_datetime("December 12th", entity_id, device_class) is None
    assert "sensor.timestamp rendered invalid date December 12th" in caplog.text
