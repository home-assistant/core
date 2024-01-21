"""Provide a mock cover platform.

Call init before using it in your tests to ensure clean test data.
"""
from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
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
                supported_features=CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
            ),
            MockCover(
                name="Set position cover",
                is_on=True,
                unique_id="unique_set_pos_cover",
                current_cover_position=50,
                supported_features=CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
                | CoverEntityFeature.SET_POSITION,
            ),
            MockCover(
                name="Simple tilt cover",
                is_on=True,
                unique_id="unique_tilt_cover",
                supported_features=CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT,
            ),
            MockCover(
                name="Set tilt position cover",
                is_on=True,
                unique_id="unique_set_pos_tilt_cover",
                current_cover_tilt_position=50,
                supported_features=CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION,
            ),
            MockCover(
                name="All functions cover",
                is_on=True,
                unique_id="unique_all_functions_cover",
                current_cover_position=50,
                current_cover_tilt_position=50,
                supported_features=CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
                | CoverEntityFeature.SET_POSITION
                | CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION,
            ),
            MockCover(
                name="Simple with opening/closing cover",
                is_on=True,
                unique_id="unique_opening_closing_cover",
                supported_features=CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
                reports_opening_closing=True,
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

    def __init__(
        self, reports_opening_closing: bool | None = None, **values: Any
    ) -> None:
        """Initialize a mock cover entity."""

        super().__init__(**values)
        self._reports_opening_closing = (
            reports_opening_closing
            if reports_opening_closing is not None
            else CoverEntityFeature.STOP in self.supported_features
        )

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if "state" in self._values and self._values["state"] == STATE_CLOSED:
            return True

        return self.current_cover_position == 0

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        if "state" in self._values:
            return self._values["state"] == STATE_OPENING

        return False

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        if "state" in self._values:
            return self._values["state"] == STATE_CLOSING

        return False

    def open_cover(self, **kwargs) -> None:
        """Open cover."""
        if self._reports_opening_closing:
            self._values["state"] = STATE_OPENING
        else:
            self._values["state"] = STATE_OPEN

    def close_cover(self, **kwargs) -> None:
        """Close cover."""
        if self._reports_opening_closing:
            self._values["state"] = STATE_CLOSING
        else:
            self._values["state"] = STATE_CLOSED

    def stop_cover(self, **kwargs) -> None:
        """Stop cover."""
        assert CoverEntityFeature.STOP in self.supported_features
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
