"""Provide a mock event platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.event import EventEntity

from tests.common import MockEntity

ENTITIES = []


class MockEventEntity(MockEntity, EventEntity):
    """Mock EventEntity class."""

    @property
    def event_types(self) -> list[str]:
        """Return a list of possible events."""
        return self._handle("event_types")


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockEventEntity(
                name="doorbell",
                unique_id="unique_doorbell",
                event_types=["short_press", "long_press"],
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)
