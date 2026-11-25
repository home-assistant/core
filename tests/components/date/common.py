"""Common helpers for date entity component tests."""

from datetime import date

from pytest_homeassistant.common import MockEntity

from homeassistant.components.date import DateEntity


class MockDateEntity(MockEntity, DateEntity):
    """Mock date class."""

    @property
    def native_value(self):
        """Return the native value of this date."""
        return self._handle("native_value")

    def set_value(self, value: date) -> None:
        """Change the date."""
        self._values["native_value"] = value
