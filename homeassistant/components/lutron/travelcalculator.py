"""Module TravelCalculator provides functionality for predicting the current position of a Cover.

E.g.:

* Given a Cover that takes 100 seconds to travel from top to bottom.
* Starting from position 90, directed to position 60 at time 0.
* At time 10 TravelCalculator will return position 80 (final position not reached).
* At time 20 TravelCalculator will return position 70 (final position not reached).
* At time 30 TravelCalculator will return position 60 (final position reached).

Borrowed from XKNX implementation: https://github.com/XKNX/xknx/blob/main/xknx/devices/travelcalculator.py release 0.9.4.
Thanks @farmio https://github.com/nagyrobi/home-assistant-custom-components-cover-rf-time-based/issues/50#issuecomment-1212172751
TODO: check vs current travelcalculator
"""

from enum import Enum
import time


class PositionType(Enum):
    """Enum class for different type of calculated positions."""

    UNKNOWN = 1
    CALCULATED = 2
    CONFIRMED = 3


class TravelStatus(Enum):
    """Enum class for travel status."""

    DIRECTION_UP = 1
    DIRECTION_DOWN = 2
    STOPPED = 3


class TravelCalculator:
    """Class for calculating the current position of a cover."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, travel_time_down, travel_time_up):
        """Initialize TravelCalculator class."""
        self.position_type = PositionType.UNKNOWN
        self.last_known_position = 0

        self.travel_time_down = travel_time_down
        self.travel_time_up = travel_time_up

        self.travel_to_position = 0
        self.travel_started_time = 0
        self.travel_direction = TravelStatus.STOPPED

        # 0 is closed, 100 is fully open
        self.position_closed = 0
        self.position_open = 100

        self.time_set_from_outside = None

    def set_position(self, position):
        """Set known position of cover."""
        self.last_known_position = position
        self.travel_to_position = position
        self.position_type = PositionType.CONFIRMED

    def stop(self):
        """Stop traveling."""
        self.last_known_position = self.current_position()
        self.travel_to_position = self.last_known_position
        self.position_type = PositionType.CALCULATED
        self.travel_direction = TravelStatus.STOPPED

    def start_travel(self, travel_to_position):
        """Start traveling to position."""
        self.stop()
        self.travel_started_time = self.current_time()
        self.travel_to_position = travel_to_position
        self.position_type = PositionType.CALCULATED

        self.travel_direction = (
            TravelStatus.DIRECTION_UP
            if travel_to_position > self.last_known_position
            else TravelStatus.DIRECTION_DOWN
        )

    def start_travel_up(self):
        """Start traveling up."""
        self.start_travel(self.position_open)

    def start_travel_down(self):
        """Start traveling down."""
        self.start_travel(self.position_closed)

    def current_position(self):
        """Return current (calculated or known) position."""
        if self.position_type == PositionType.CALCULATED:
            return self._calculate_position()
        return self.last_known_position

    def is_traveling(self):
        """Return if cover is traveling."""
        return self.current_position() != self.travel_to_position

    def position_reached(self):
        """Return if cover has reached designated position."""
        return self.current_position() == self.travel_to_position

    def is_open(self):
        """Return if cover is (fully) open."""
        return self.current_position() == self.position_open

    def is_closed(self):
        """Return if cover is (fully) closed."""
        return self.current_position() == self.position_closed

    def _calculate_position(self):
        """Return calculated position."""
        relative_position = self.travel_to_position - self.last_known_position

        def position_reached_or_exceeded(relative_position):
            """Return if designated position was reached."""
            if (
                relative_position >= 0
                and self.travel_direction == TravelStatus.DIRECTION_DOWN
            ):
                return True
            if (
                relative_position <= 0
                and self.travel_direction == TravelStatus.DIRECTION_UP
            ):
                return True
            return False

        if position_reached_or_exceeded(relative_position):
            return self.travel_to_position

        travel_time = self._calculate_travel_time(relative_position)
        if self.current_time() > self.travel_started_time + travel_time:
            return self.travel_to_position
        progress = (self.current_time() - self.travel_started_time) / travel_time
        position = self.last_known_position + relative_position * progress
        return int(position)

    def _calculate_travel_time(self, relative_position):
        """Calculate time to travel to relative position."""
        travel_direction = (
            TravelStatus.DIRECTION_UP
            if relative_position > 0
            else TravelStatus.DIRECTION_DOWN
        )
        travel_time_full = (
            self.travel_time_up
            if travel_direction == TravelStatus.DIRECTION_UP
            else self.travel_time_down
        )
        travel_range = self.position_open - self.position_closed

        return travel_time_full * abs(relative_position) / travel_range

    def current_time(self):
        """Get current time. May be modified from outside (for unit tests)."""
        # time_set_from_outside is  used within unit tests
        if self.time_set_from_outside is not None:
            return self.time_set_from_outside
        return time.time()

    def __eq__(self, other):
        """Equal operator."""
        return self.__dict__ == other.__dict__
