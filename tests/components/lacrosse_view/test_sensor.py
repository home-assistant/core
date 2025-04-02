"""Test the LaCrosse View sensors."""

from typing import Any
from unittest.mock import patch

from lacrosse_view import Sensor
import pytest

from homeassistant.components.lacrosse_view import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    MOCK_ENTRY_DATA,
    TEST_ALREADY_FLOAT_SENSOR,
    TEST_ALREADY_INT_SENSOR,
    TEST_FLOAT_SENSOR,
    TEST_MISSING_FIELD_DATA_SENSOR,
    TEST_NO_FIELD_SENSOR,
    TEST_NO_PERMISSION_SENSOR,
    TEST_NO_READINGS_SENSOR,
    TEST_OTHER_ERROR_SENSOR,
    TEST_SENSOR,
    TEST_STRING_SENSOR,
    TEST_UNITS_OVERRIDE_SENSOR,
    TEST_UNSUPPORTED_SENSOR,
)

from tests.common import MockConfigEntry


async def test_entities_added(hass: HomeAssistant) -> None:
    """Test the entities are added."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    sensor = TEST_SENSOR.model_copy()
    status = sensor.data
    sensor.data = None

    with (
        patch("lacrosse_view.LaCrosse.login", return_value=True),
        patch("lacrosse_view.LaCrosse.get_devices", return_value=[sensor]),
        patch("lacrosse_view.LaCrosse.get_sensor_status", return_value=status),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_temperature")


async def test_sensor_permission(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if it raises a warning when there is no permission to read the sensor."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    sensor = TEST_NO_PERMISSION_SENSOR.model_copy()
    status = sensor.data
    sensor.data = None

    with (
        patch("lacrosse_view.LaCrosse.login", return_value=True),
        patch(
            "lacrosse_view.LaCrosse.get_devices",
            return_value=[sensor],
        ),
        patch("lacrosse_view.LaCrosse.get_sensor_status", return_value=status),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR
    assert not hass.states.get("sensor.test_temperature")
    assert "This account does not have permission to read Test" in caplog.text


async def test_field_not_supported(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if it raises a warning when the field is not supported."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    sensor = TEST_UNSUPPORTED_SENSOR.model_copy()
    status = sensor.data
    sensor.data = None

    with (
        patch("lacrosse_view.LaCrosse.login", return_value=True),
        patch("lacrosse_view.LaCrosse.get_devices", return_value=[sensor]),
        patch("lacrosse_view.LaCrosse.get_sensor_status", return_value=status),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_some_unsupported_field") is None
    assert "Unsupported sensor field" in caplog.text


@pytest.mark.parametrize(
    ("test_input", "expected", "entity_id"),
    [
        (TEST_FLOAT_SENSOR, "2.3", "temperature"),
        (TEST_STRING_SENSOR, "dry", "wet_dry"),
        (TEST_ALREADY_FLOAT_SENSOR, "-16.5", "heat_index"),
        (TEST_ALREADY_INT_SENSOR, "2", "wind_speed"),
        (TEST_UNITS_OVERRIDE_SENSOR, "-16.6111111111111", "temperature"),
    ],
)
async def test_field_types(
    hass: HomeAssistant, test_input: Sensor, expected: Any, entity_id: str
) -> None:
    """Test the different data types for fields."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    sensor = test_input.model_copy()
    status = sensor.data
    sensor.data = None

    with (
        patch("lacrosse_view.LaCrosse.login", return_value=True),
        patch(
            "lacrosse_view.LaCrosse.get_devices",
            return_value=[test_input],
        ),
        patch("lacrosse_view.LaCrosse.get_sensor_status", return_value=status),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert hass.states.get(f"sensor.test_{entity_id}").state == expected


async def test_no_field(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test behavior when the expected field is not present."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    sensor = TEST_NO_FIELD_SENSOR.model_copy()
    status = sensor.data
    sensor.data = None

    with (
        patch("lacrosse_view.LaCrosse.login", return_value=True),
        patch(
            "lacrosse_view.LaCrosse.get_devices",
            return_value=[sensor],
        ),
        patch("lacrosse_view.LaCrosse.get_sensor_status", return_value=status),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_temperature").state == "unavailable"


async def test_field_data_missing(hass: HomeAssistant) -> None:
    """Test behavior when field data is missing."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    sensor = TEST_MISSING_FIELD_DATA_SENSOR.model_copy()
    status = sensor.data
    sensor.data = None

    with (
        patch("lacrosse_view.LaCrosse.login", return_value=True),
        patch(
            "lacrosse_view.LaCrosse.get_devices",
            return_value=[sensor],
        ),
        patch("lacrosse_view.LaCrosse.get_sensor_status", return_value=status),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_temperature").state == "unknown"


async def test_no_readings(hass: HomeAssistant) -> None:
    """Test behavior when there are no readings."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    sensor = TEST_NO_READINGS_SENSOR.model_copy()
    status = sensor.data
    sensor.data = None

    with (
        patch("lacrosse_view.LaCrosse.login", return_value=True),
        patch(
            "lacrosse_view.LaCrosse.get_devices",
            return_value=[sensor],
        ),
        patch("lacrosse_view.LaCrosse.get_sensor_status", return_value=status),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_temperature").state == "unavailable"


async def test_other_error(hass: HomeAssistant) -> None:
    """Test behavior when there is an error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    sensor = TEST_OTHER_ERROR_SENSOR.model_copy()
    status = sensor.data
    sensor.data = None

    with (
        patch("lacrosse_view.LaCrosse.login", return_value=True),
        patch(
            "lacrosse_view.LaCrosse.get_devices",
            return_value=[sensor],
        ),
        patch("lacrosse_view.LaCrosse.get_sensor_status", return_value=status),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY
