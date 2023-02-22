"""Provide a mock cover platform.

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

ENTITIES = []


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
                supported_features=SUPPORT_OPEN | SUPPORT_CLOSE,
            ),
            MockCover(
                name="Set position cover",
                is_on=True,
                unique_id="unique_set_pos_cover",
                current_cover_position=50,
                supported_features=SUPPORT_OPEN
                | SUPPORT_CLOSE
                | SUPPORT_STOP
                | SUPPORT_SET_POSITION,
            ),
            MockCover(
                name="Simple tilt cover",
                is_on=True,
                unique_id="unique_tilt_cover",
                supported_features=SUPPORT_OPEN
                | SUPPORT_CLOSE
                | SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT,
            ),
            MockCover(
                name="Set tilt position cover",
                is_on=True,
                unique_id="unique_set_pos_tilt_cover",
                current_cover_tilt_position=50,
                supported_features=SUPPORT_OPEN
                | SUPPORT_CLOSE
                | SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT
                | SUPPORT_STOP_TILT
                | SUPPORT_SET_TILT_POSITION,
            ),
            MockCover(
                name="All functions cover",
                is_on=True,
                unique_id="unique_all_functions_cover",
                current_cover_position=50,
                current_cover_tilt_position=50,
                supported_features=SUPPORT_OPEN
                | SUPPORT_CLOSE
                | SUPPORT_STOP
                | SUPPORT_SET_POSITION
                | SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT
                | SUPPORT_STOP_TILT
                | SUPPORT_SET_TILT_POSITION,
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
        """Open cover."""
        if self.supported_features & SUPPORT_STOP:
            self._values["state"] = STATE_OPENING
        else:
            self._values["state"] = STATE_OPEN

    def close_cover(self, **kwargs) -> None:
        """Close cover."""
        if self.supported_features & SUPPORT_STOP:
            self._values["state"] = STATE_CLOSING
        else:
            self._values["state"] = STATE_CLOSED

    def stop_cover(self, **kwargs) -> None:
        """Stop cover."""
        self._values["state"] = STATE_CLOSED if self.is_closed else STATE_OPEN

    @property
    def state(self):
        """Fake State."""
        return CoverEntity.state.fget(self)

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        return self._handle("current_cover_position")

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return self._handle("current_cover_tilt_position")
