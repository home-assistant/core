"""
Provide a mock cover platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.cover import CoverDevice

from tests.common import MockEntity

ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockCover(name=f"Simple cover", is_on=True, unique_id=f"unique_cover"),
            MockCover(
                name=f"Set position cover",
                is_on=True,
                unique_id=f"unique_set_pos_cover",
                current_cover_position=50,
            ),
            MockCover(
                name=f"Set tilt position cover",
                is_on=True,
                unique_id=f"unique_set_pos_tilt_cover",
                current_cover_tilt_position=50,
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)


class MockCover(MockEntity, CoverDevice):
    """Mock Cover class."""

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return False

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        return self._handle("current_cover_position")

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return self._handle("current_cover_tilt_position")
