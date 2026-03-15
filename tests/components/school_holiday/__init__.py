"""Tests for the School Holiday integration."""

from homeassistant.components.school_holiday.coordinator import SchoolHolidayCoordinator

from tests.common import MockConfigEntry

type MockSchoolHolidayConfigEntry = MockConfigEntry[SchoolHolidayCoordinator]
