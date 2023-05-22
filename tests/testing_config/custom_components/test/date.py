"""Provide a mock date platform.

Call init before using it in your tests to ensure clean test data.
"""
from datetime import date

from homeassistant.components.date import DateEntity

from tests.common import MockEntity

UNIQUE_DATE = "unique_date"

ENTITIES = []


class MockDateEntity(MockEntity, DateEntity):
    """Mock date class."""

    @property
    def native_value(self):
        """Return the native value of this date."""
        return self._handle("native_value")

    def set_value(self, value: date) -> None:
        """Change the date."""
        self._values["native_value"] = value


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockDateEntity(
                name="test",
                unique_id=UNIQUE_DATE,
                native_value=date(2020, 1, 1),
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
