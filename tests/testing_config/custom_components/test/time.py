"""Provide a mock time platform.

Call init before using it in your tests to ensure clean test data.
"""
from datetime import time

from homeassistant.components.time import TimeEntity

from tests.common import MockEntity

UNIQUE_TIME = "unique_time"

ENTITIES = []


class MockTimeEntity(MockEntity, TimeEntity):
    """Mock time class."""

    @property
    def native_value(self):
        """Return the native value of this time."""
        return self._handle("native_value")

    def set_value(self, value: time) -> None:
        """Change the time."""
        self._values["native_value"] = value


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockTimeEntity(
                name="test",
                unique_id=UNIQUE_TIME,
                native_value=time(1, 2, 3),
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
