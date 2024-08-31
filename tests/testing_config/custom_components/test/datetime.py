"""Provide a mock time platform.

Call init before using it in your tests to ensure clean test data.
"""
from datetime import UTC, datetime

from homeassistant.components.datetime import DateTimeEntity

from tests.common import MockEntity

UNIQUE_DATETIME = "unique_datetime"

ENTITIES = []


class MockDateTimeEntity(MockEntity, DateTimeEntity):
    """Mock date/time class."""

    @property
    def native_value(self):
        """Return the native value of this date/time."""
        return self._handle("native_value")

    def set_value(self, value: datetime) -> None:
        """Change the time."""
        self._values["native_value"] = value


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockDateTimeEntity(
                name="test",
                unique_id=UNIQUE_DATETIME,
                native_value=datetime(2020, 1, 1, 1, 2, 3, tzinfo=UTC),
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
