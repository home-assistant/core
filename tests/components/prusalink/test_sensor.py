"""Test Prusalink sensors."""

from datetime import datetime, timezone
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def setup_sensor_platform_only():
    """Only setup sensor platform."""
    with patch(
        "homeassistant.components.prusalink.PLATFORMS", [Platform.SENSOR]
    ), patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        PropertyMock(return_value=True),
    ):
        yield


async def test_sensors_no_job(hass: HomeAssistant, mock_config_entry, mock_api) -> None:
    """Test sensors while no job active."""
    assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("sensor.mock_title")
    assert state is not None
    assert state.state == "idle"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == [
        "cancelling",
        "idle",
        "paused",
        "pausing",
        "printing",
    ]

    state = hass.states.get("sensor.mock_title_heatbed")
    assert state is not None
    assert state.state == "41.9"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_nozzle_temperature")
    assert state is not None
    assert state.state == "47.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_progress")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"

    state = hass.states.get("sensor.mock_title_filename")
    assert state is not None
    assert state.state == "unavailable"

    state = hass.states.get("sensor.mock_title_print_start")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.mock_title_print_finish")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP


async def test_sensors_active_job(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    mock_printer_api,
    mock_job_api_printing,
) -> None:
    """Test sensors while active job."""
    with patch(
        "homeassistant.components.prusalink.sensor.utcnow",
        return_value=datetime(2022, 8, 27, 14, 0, 0, tzinfo=timezone.utc),
    ):
        assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("sensor.mock_title")
    assert state is not None
    assert state.state == "printing"

    state = hass.states.get("sensor.mock_title_progress")
    assert state is not None
    assert state.state == "37.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"

    state = hass.states.get("sensor.mock_title_filename")
    assert state is not None
    assert state.state == "TabletStand3.gcode"

    state = hass.states.get("sensor.mock_title_print_start")
    assert state is not None
    assert state.state == "2022-08-27T01:46:53+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.mock_title_print_finish")
    assert state is not None
    assert state.state == "2022-08-28T10:17:00+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP
