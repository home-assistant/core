"""Common helpers for time entity component tests."""

from datetime import time

from homeassistant.components.time import TimeEntity

from tests.common import MockEntity


class MockTimeEntity(MockEntity, TimeEntity):
    """Mock time class."""

    @property
    def native_value(self) -> time | None:
        """Return the current time."""
        return self._handle("native_value")

    def set_value(self, value: time) -> None:
        """Change the time."""
        self._values["native_value"] = value
