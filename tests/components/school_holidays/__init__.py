"""Tests for the school holidays integration."""

from homeassistant.components.school_holidays.coordinator import (
    SchoolHolidaysCoordinator,
)

from tests.common import MockConfigEntry

type MockSchoolHolidaysConfigEntry = MockConfigEntry[SchoolHolidaysCoordinator]
