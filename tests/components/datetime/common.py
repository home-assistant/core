"""Common helpers for the datetime entity component tests."""

from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity

from tests.common import MockEntity


class MockDateTimeEntity(MockEntity, DateTimeEntity):
    """Mock date/time class."""

    @property
    def native_value(self):
        """Return the native value of this date/time."""
        return self._handle("native_value")

    def set_value(self, value: datetime) -> None:
        """Change the time."""
        self._values["native_value"] = value
