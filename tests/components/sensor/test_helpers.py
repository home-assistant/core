"""Tests for sensor helpers."""

import pytest

from homeassistant.components.sensor import DOMAIN, SensorDeviceClass, SensorStateClass
from homeassistant.components.sensor.helpers import (
    async_parse_date_datetime,
    create_sensor_device_class_select_selector,
    create_sensor_state_class_select_selector,
)


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


def test_create_sensor_device_class_select_selector() -> None:
    "Test Create sensor state class select selector helper."
    selector = create_sensor_device_class_select_selector()
    assert selector.config["options"] == list(SensorDeviceClass)
    assert selector.config["translation_domain"] == DOMAIN
    assert selector.config["translation_key"] == "device_class"
    assert selector.config["sort"]
    assert not selector.config["custom_value"]


def test_create_sensor_state_class_select_selector() -> None:
    "Test Create sensor state class select selector helper."
    selector = create_sensor_state_class_select_selector()
    assert selector.config["options"] == list(SensorStateClass)
    assert selector.config["translation_domain"] == DOMAIN
    assert selector.config["translation_key"] == "state_class"
    assert selector.config["sort"]
    assert not selector.config["custom_value"]
