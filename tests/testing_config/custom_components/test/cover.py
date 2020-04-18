"""
Provide a mock cover platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverDevice,
)

from tests.common import MockEntity

ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockCover(
                name=f"Simple cover",
                is_on=True,
                unique_id=f"unique_cover",
                supports_tilt=False,
            ),
            MockCover(
                name=f"Set position cover",
                is_on=True,
                unique_id=f"unique_set_pos_cover",
                current_cover_position=50,
                supports_tilt=False,
            ),
            MockCover(
                name=f"Set tilt position cover",
                is_on=True,
                unique_id=f"unique_set_pos_tilt_cover",
                current_cover_tilt_position=50,
                supports_tilt=True,
            ),
            MockCover(
                name=f"Tilt cover",
                is_on=True,
                unique_id=f"unique_tilt_cover",
                supports_tilt=True,
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

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

        if self._handle("supports_tilt"):
            supported_features |= (
                SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | SUPPORT_STOP_TILT
            )

        if self.current_cover_position is not None:
            supported_features |= SUPPORT_SET_POSITION

        if self.current_cover_tilt_position is not None:
            supported_features |= (
                SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT
                | SUPPORT_STOP_TILT
                | SUPPORT_SET_TILT_POSITION
            )

        return supported_features
