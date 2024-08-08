"""Tests for prometheus test helpers."""

from __future__ import annotations

from .helpers import MetricsTestHelper


def test_metric_test_helper_formats_simple_metric_string() -> None:
    """Test using helper to format a simple metric string with no value included."""
    assert MetricsTestHelper._get_metric_string(
        "homeassistant_sensor_temperature_celsius",
        "sensor",
        "Outside Temperature",
        "outside_temperature",
    ) == (
        "homeassistant_sensor_temperature_celsius{"
        'area="",'
        'device_class="",'
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature",'
        'object_id="outside_temperature"}'
    )


def test_metric_test_helper_formats_simple_metric_string_with_value() -> None:
    """Test using helper to format a simple metric string but with a value included."""
    assert MetricsTestHelper._get_metric_string(
        "homeassistant_sensor_temperature_celsius",
        "sensor",
        "Outside Temperature",
        "outside_temperature",
        metric_value="17.2",
    ) == (
        "homeassistant_sensor_temperature_celsius{"
        'area="",'
        'device_class="",'
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature",'
        'object_id="outside_temperature"} 17.2'
    )


def test_metric_test_helper_formats_simple_metric_string_with_device_class() -> None:
    """Test using helper to format a simple metric string and set a string device_class."""
    assert MetricsTestHelper._get_metric_string(
        "homeassistant_sensor_temperature_celsius",
        "sensor",
        "Outside Temperature",
        "outside_temperature",
        device_class="temperature",
    ) == (
        "homeassistant_sensor_temperature_celsius{"
        'area="",'
        'device_class="temperature",'
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature",'
        'object_id="outside_temperature"}'
    )
