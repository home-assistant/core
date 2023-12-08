"""Provide a mock valve platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.valve import ValveEntity, ValveEntityFeature

from tests.common import MockEntity

ENTITIES = []


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        []
        if empty
        else [
            MockBinaryValve(
                name="Simple valve",
                is_on=True,
                unique_id="unique_valve",
                supported_features=ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE,
            ),
            MockPositionValve(
                name="Set position valve",
                is_on=True,
                unique_id="unique_set_pos_valve",
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


class MockBinaryValve(MockEntity, ValveEntity):
    """Mock binary Valve class."""

    _attr_reports_position = False
    _attr_is_closed = False

    def open_valve(self) -> None:
        """Open the valve."""
        self._attr_is_closed = False

    def close_valve(self) -> None:
        """Close the valve."""
        self._attr_is_closed = True


class MockPositionValve(MockEntity, ValveEntity):
    """Mock Valve class."""

    _attr_reports_position = True
    _attr_current_valve_position = 50

    _target_valve_position: int

    def set_valve_position(self, position: int) -> None:
        """Set the valve to opening or closing towards a target percentage."""
        if position > self._attr_current_valve_position:
            self._attr_is_closing = False
            self._attr_is_opening = True
        else:
            self._attr_is_closing = True
            self._attr_is_opening = False
        self._target_valve_position = position
        self.async_write_ha_state()

    def stop_valve(self) -> None:
        """Stop the valve."""
        self._attr_is_closing = False
        self._attr_is_opening = False
        self._target_valve_position = None
        self.async_write_ha_state()

    async def finish_movement(self):
        """Set the value to the saved target and removes intermediate states."""
        self._attr_current_valve_position = self._target_valve_position
        self._attr_is_closing = False
        self._attr_is_opening = False
        self.async_write_ha_state()
