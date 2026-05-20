"""Test binary sensor platform for School Holiday integration."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.school_holiday.binary_sensor import (
    SchoolHolidayBinarySensor,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_COUNTRY, TEST_ENTRY_ID, TEST_REGION, TEST_SENSOR_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api_response,
) -> None:
    """Test binary sensor setup and entity registration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that binary sensor entity is registered.
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    binary_sensor_entries = [
        e for e in entity_entries if e.domain == Platform.BINARY_SENSOR
    ]
    assert len(binary_sensor_entries) == 1

    entry = binary_sensor_entries[0]
    assert entry.domain == Platform.BINARY_SENSOR


def test_binary_sensor_entity_available() -> None:
    """Test binary sensor entity availability with successful last update."""
    coordinator = MagicMock()
    coordinator.last_update_success = True

    entity = SchoolHolidayBinarySensor(
        coordinator, TEST_SENSOR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    assert entity.available is True


def test_binary_sensor_entity_unavailable() -> None:
    """Test binary sensor entity availability with unsuccessful last update."""
    coordinator = MagicMock()
    coordinator.last_update_success = False

    entity = SchoolHolidayBinarySensor(
        coordinator, TEST_SENSOR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    assert entity.available is False


def test_binary_sensor_entity_attributes() -> None:
    """Test binary sensor entity attributes."""
    coordinator = MagicMock()
    coordinator.data = []

    entity = SchoolHolidayBinarySensor(
        coordinator, TEST_SENSOR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    assert entity._country == TEST_COUNTRY
    assert entity._region == TEST_REGION
    assert entity.unique_id == f"{TEST_ENTRY_ID}_sensor"


def test_binary_sensor_entity_is_on_during_school_holiday(
    mock_school_holiday_data,
) -> None:
    """Test binary sensor entity state during a school holiday."""
    coordinator = MagicMock()
    # Use the summer holiday, which spans 2026-07-18 to 2026-08-30.
    coordinator.data = [mock_school_holiday_data[0]]

    entity = SchoolHolidayBinarySensor(
        coordinator, TEST_SENSOR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"

    with patch(
        "homeassistant.components.school_holiday.binary_sensor.date"
    ) as mock_date:
        # Test with random date during school holiday.
        mock_date.today.return_value = date(2026, 8, 22)
        assert entity.is_on is True


def test_binary_sensor_entity_is_off_outside_school_holidays(
    mock_school_holiday_data,
) -> None:
    """Test binary sensor entity state outside school holidays."""
    coordinator = MagicMock()
    # Use both school holidays, which spans 2026-07-18 to 2026-08-30 and 2026-10-17 to 2026-10-25.
    coordinator.data = mock_school_holiday_data

    entity = SchoolHolidayBinarySensor(
        coordinator, TEST_SENSOR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"

    with patch(
        "homeassistant.components.school_holiday.binary_sensor.date"
    ) as mock_date:
        # Test with random date before school holidays.
        mock_date.today.return_value = date(2026, 6, 25)
        assert entity.is_on is False

        # Test with random date between school holidays.
        mock_date.today.return_value = date(2026, 9, 5)
        assert entity.is_on is False

        # Test with random date after school holidays.
        mock_date.today.return_value = date(2026, 10, 29)
        assert entity.is_on is False


def test_binary_sensor_entity_is_off_without_school_holidays() -> None:
    """Test binary sensor entity state without school holidays."""
    coordinator = MagicMock()
    coordinator.data = []

    entity = SchoolHolidayBinarySensor(
        coordinator, TEST_SENSOR_NAME, TEST_COUNTRY, TEST_REGION, TEST_ENTRY_ID
    )

    assert entity.is_on is False
