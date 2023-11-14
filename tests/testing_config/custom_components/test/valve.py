"""Provide a mock valve platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.valve import ValveEntity, ValveEntityFeature
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
            MockValve(
                name="Simple valve",
                is_on=True,
                unique_id="unique_valve",
                supported_features=ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE,
            ),
            MockValve(
                name="Set position valve",
                is_on=True,
                unique_id="unique_set_pos_valve",
                current_valve_position=50,
                supported_features=ValveEntityFeature.OPEN
                | ValveEntityFeature.CLOSE
                | ValveEntityFeature.STOP
                | ValveEntityFeature.SET_POSITION,
            ),
        ]
    )


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Return mock entities."""
    async_add_entities_callback(ENTITIES)


class MockValve(MockEntity, ValveEntity):
    """Mock Valve class."""

    @property
    def is_closed(self):
        """Return if the valve is closed or not."""
        if self.supported_features & ValveEntityFeature.STOP:
            return self.current_valve_position == 0

        if "state" in self._values:
            return self._values["state"] == STATE_CLOSED
        return False

    @property
    def is_opening(self):
        """Return if the valve is opening or not."""
        if self.supported_features & ValveEntityFeature.STOP:
            if "state" in self._values:
                return self._values["state"] == STATE_OPENING

        return False

    @property
    def is_closing(self):
        """Return if the valve is closing or not."""
        if self.supported_features & ValveEntityFeature.STOP:
            if "state" in self._values:
                return self._values["state"] == STATE_CLOSING

        return False

    def open_valve(self) -> None:
        """Open valve."""
        if self.supported_features & ValveEntityFeature.STOP:
            self._values["state"] = STATE_OPENING
        else:
            self._values["state"] = STATE_OPEN

    def close_valve(self) -> None:
        """Close valve."""
        if self.supported_features & ValveEntityFeature.STOP:
            self._values["state"] = STATE_CLOSING
        else:
            self._values["state"] = STATE_CLOSED

    def stop_valve(self) -> None:
        """Stop valve."""
        self._values["state"] = STATE_CLOSED if self.is_closed else STATE_OPEN

    @property
    def state(self):
        """Fake State."""
        return ValveEntity.state.fget(self)

    @property
    def current_valve_position(self):
        """Return current position of valve."""
        return self._handle("current_valve_position")
