"""Tests for the state buffer."""

from datetime import datetime, timedelta
from threading import Lock, Thread
import unittest

from homeassistant.components.statistics.state_buffer import BufferedState, StateBuffer


class StateBufferTestMethods(unittest.TestCase):
    """Test class for the state buffer."""

    def __init__(self, test_name: str) -> None:
        """Create an instance of the state buffer tests."""

        super().__init__(test_name)
        self._thread_value: float = 0
        self._lock: Lock = Lock()
        self._buffer: StateBuffer
        self._now: datetime

    def _init(self, size_limit: int | None, age_limit: timedelta | None) -> None:
        self._now = datetime(2000, 1, 1)
        self._buffer = StateBuffer(size_limit, age_limit)

    def _generate_states(
        self, min: int, max: int, value: float, expected_return_value: int | None
    ):
        step: int = 1
        if min > max:
            step = -1
        for n in range(min, max + step, step):
            return_value: int = self._buffer.insert(
                BufferedState(
                    self._now + timedelta(minutes=n),
                    value + ((1 + (step * (n - min))) / 1000.0),
                    True,
                )
            )
            if expected_return_value is not None:
                assert return_value == expected_return_value, (
                    "expected return value doesn't match "
                    + str(return_value)
                    + " vs. "
                    + str(expected_return_value)
                )

    def _generate_states_thread(self) -> None:
        with self._lock:
            self._thread_value += 1
            value: float = self._thread_value
        for n in range(10000):
            self._buffer.insert(
                BufferedState(datetime.now(), value + (n / 100000.0), True)
            )

    def _assert_buffer_matches(self, match_list: list[float]) -> bool:
        matches: bool = True
        buffer_list: list[float] = self._buffer.states(None).values
        if len(match_list) != len(buffer_list):
            matches = False
        else:
            for i, entry in enumerate(match_list):
                if buffer_list[i] != entry:
                    matches = False
        assert matches, (
            "values dont match "
            + ",".join(map(str, buffer_list))
            + " vs. "
            + ",".join(map(str, match_list))
        )

    def test_order(self) -> None:
        """Test whether values will be added in the right order."""
        self._init(None, None)
        self._generate_states(1, 3, 1.0, 1)
        self._generate_states(-1, -3, 2.0, -1)
        self._generate_states(-3, 3, 3.0, None)  # the inner values will be ignored
        self._generate_states(4, 6, 4.0, 1)
        self._assert_buffer_matches(
            (
                3.001,
                2.003,
                2.002,
                2.001,
                1.001,
                1.002,
                1.003,
                3.007,
                4.001,
                4.002,
                4.003,
            )
        )

    def test_length_limit(self) -> None:
        """Test the length limit."""
        self._init(3, None)
        self._generate_states(1, 5, 1.0, 1)
        self._assert_buffer_matches((1.003, 1.004, 1.005))

    def test_time_limit(self) -> None:
        """Test the age limit."""
        self._init(None, timedelta(minutes=2.5))
        self._generate_states(1, 5, 1.0, 1)
        self._buffer.states(self._now + timedelta(minutes=5))
        self._assert_buffer_matches((1.002, 1.003, 1.004, 1.005))

    def test_time_limit_edge_case(self) -> None:
        """Test the age limit with one value exactly at the end of the interval."""
        self._init(None, timedelta(minutes=2))
        self._generate_states(1, 5, 1.0, 1)
        self._buffer.states(self._now + timedelta(minutes=5))
        self._assert_buffer_matches((1.003, 1.004, 1.005))

    def test_sync(self) -> None:
        """Test parallel access to the list."""
        self._init(None, None)
        threads: list[Thread] = []
        for i in range(10):  # noqa: B007
            thread: Thread = Thread(target=self._generate_states_thread)
            threads.append(thread)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        timestamps: list[datetime] = self._buffer.states(None).timestamps
        buffer_size: int = len(timestamps)
        assert buffer_size < 100000, "unexpected buffer size: " + str(buffer_size)
        for i in range(len(timestamps) - 1):
            assert timestamps[i + 1] >= timestamps[i], (
                "list not correctly ordered at position " + str(i)
            )


if __name__ == "__main__":
    unittest.main()
