"""The state buffer stores the data needed for the statistic functions.

It makes sure that the data is always consistent,
even though different threads are interacting with it.
"""

from collections import deque
from datetime import datetime, timedelta
import logging
from threading import Lock

_LOGGER = logging.getLogger(__name__)


class BufferedState:
    """The state of a sensor."""

    def __init__(
        self, changed_at: datetime, value: float, is_valid: bool | None
    ) -> None:
        """Create a state to be stored in the buffer."""
        self.changed_at = changed_at
        self.value = value
        self.is_valid = is_valid


class StateData:
    """The data that represent the buffer state at a certain point in time."""

    def __init__(
        self,
        timestamps: list[datetime],
        values: list[float],
        update_time: datetime,
        is_valid: bool | None,
    ) -> None:
        """Create the state data."""
        self.timestamps = timestamps
        self.values = values
        self.update_time = update_time
        self.is_valid = is_valid


class StateBuffer:
    """A buffer for states that takes care of synchronization."""

    def __init__(
        self,
        size_limit: int | None,
        age_limit: timedelta | None,
    ) -> None:
        """Create a buffer."""
        self._lock: Lock = Lock()
        self._size_limit: int | None = size_limit
        self._age_limit: timedelta | None = age_limit
        self._buffer: deque[BufferedState] = deque(maxlen=self._size_limit)

    def insert(self, buffer_state: BufferedState) -> int:
        """Insert new values into the buffer."""
        result: int = 0
        with self._lock:
            if len(self._buffer) == 0:
                self._buffer.append(buffer_state)
                result = 1
            else:
                newest_change: datetime = self._buffer[len(self._buffer) - 1].changed_at
                if buffer_state.changed_at >= newest_change:
                    self._buffer.append(buffer_state)
                    result = 1
                else:
                    oldest_change: datetime = self._buffer[0].changed_at
                    if oldest_change >= buffer_state.changed_at:
                        if (self._size_limit is None) or (
                            len(self._buffer) < self._size_limit
                        ):
                            self._buffer.appendleft(buffer_state)
                            result = -1
                    else:
                        # values to be added may not be inside the time interval covered by the buffer
                        _LOGGER.error(
                            "Value ignored: %s is between %s and %s",
                            buffer_state.changed_at,
                            oldest_change,
                            newest_change,
                        )
        return result

    def _remove_expired(self, update_time: datetime) -> None:
        if self._age_limit:
            _LOGGER.debug(
                "removing expired values older then %s (current time %s)",
                self._age_limit,
                update_time,
            )
            done: bool = False
            while not done:
                if len(self._buffer) <= 1:
                    done = True
                elif (update_time - self._buffer[1].changed_at) >= self._age_limit:
                    self._buffer.popleft()
                else:
                    done = True

    def states(self, update_time: datetime) -> StateData:
        """Remove expired states and return the states that are left."""
        is_valid: bool | None = True
        timestamps: list[datetime] = []
        values: list[float] = []
        with self._lock:
            if update_time:
                self._remove_expired(update_time)
            for buffered_state in self._buffer:
                if buffered_state.is_valid:
                    timestamps.append(buffered_state.changed_at)
                    values.append(buffered_state.value)
                is_valid = buffered_state.is_valid
        return StateData(timestamps, values, update_time, is_valid)

    def next_expiry_timestamp(self, update_time: datetime) -> datetime | None:
        """Get the timestamp of the next item that will expire."""
        result: datetime | None = None
        with self._lock:
            if (len(self._buffer) > 0) and self._age_limit:
                if self._buffer[0].changed_at + self._age_limit == update_time:
                    # this is an edge case where there is no expired value in the list
                    # this means the first value is exactly at the beginning of the interval
                    result = self._buffer[0].changed_at
                elif len(self._buffer) > 1:
                    # the first value is already expired, so the next to expire is the second one
                    result = self._buffer[1].changed_at
        return result
