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
    CoverEntity,
)
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING

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
                name="Simple cover",
                is_on=True,
                unique_id="unique_cover",
                supports_tilt=False,
            ),
            MockCover(
                name="Set position cover",
                is_on=True,
                unique_id="unique_set_pos_cover",
                current_cover_position=50,
                supports_tilt=False,
            ),
            MockCover(
                name="Set tilt position cover",
                is_on=True,
                unique_id="unique_set_pos_tilt_cover",
                current_cover_tilt_position=50,
                supports_tilt=True,
            ),
            MockCover(
                name="Tilt cover",
                is_on=True,
                unique_id="unique_tilt_cover",
                supports_tilt=True,
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)


class MockCover(MockEntity, CoverEntity):
    """Mock Cover class."""

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self.supported_features & SUPPORT_STOP:
            return self.current_cover_position == 0

        if "state" in self._values:
            return self._values["state"] == STATE_CLOSED
        return False

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        if self.supported_features & SUPPORT_STOP:
            if "state" in self._values:
                return self._values["state"] == STATE_OPENING

        return False

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        if self.supported_features & SUPPORT_STOP:
            if "state" in self._values:
                return self._values["state"] == STATE_CLOSING

        return False

    def open_cover(self, **kwargs) -> None:
        """Open cover. This usually needs a thread that simulates the state change from OPENING to OPEN."""
        if self.supported_features & SUPPORT_STOP:
            self._values["state"] = STATE_OPENING
        else:
            self._values["state"] = STATE_OPEN

    def close_cover(self, **kwargs) -> None:
        """Close cover. This usually needs a thread that simulates the state change from CLOSING to CLOSED."""
        if self.supported_features & SUPPORT_STOP:
            self._values["state"] = STATE_CLOSING
        else:
            self._values["state"] = STATE_CLOSED

    def stop_cover(self, **kwargs) -> None:
        """Stop cover. this is used to simulate the state change which is missing in open_cover and close_cover."""
        if self.is_opening:
            self._values["state"] = STATE_OPEN
            self._values["current_cover_position"] = 100
        elif self.is_closing:
            self._values["state"] = STATE_CLOSED
            self._values["current_cover_position"] = 0
        else:
            self._values["state"] = STATE_OPEN if self.is_closed else STATE_CLOSED

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
