"""Schedule metrics.

The `ScheduleMetrics` class is responsible for recording and calculating various metrics related to a schedule. It keeps track of arrival times, start times, end times, wait times, execution times, idle times, and parallelism of routines in a schedule.

Example usage:
    sm = ScheduleMetrics("FIFO")
    sm.record_routine_arrival("routine1", datetime.now(), {"action1", "action2"})
    sm.record_action_event(datetime.now(), "entity1", "action1", True)
    sm.record_action_event(datetime.now(), "entity1", "action1", False)
    avg_wait_time = sm.avg_wait_time
    avg_latency = sm.avg_latency
    parallelism = sm.parallelism

"""

import copy
from datetime import datetime, timedelta
from typing import Optional

from homeassistant.const import (
    MAX_AVG_PARALLELISM,
    MAX_P05_PARALLELISM,
    MIN_AVG_IDLE_TIME,
    MIN_AVG_RTN_LATENCY,
    MIN_AVG_RTN_WAIT_TIME,
    MIN_LENGTH,
    MIN_P95_IDLE_TIME,
    MIN_P95_RTN_LATENCY,
    MIN_P95_RTN_WAIT_TIME,
    MIN_RTN_EXEC_TIME_STD_DEV,
)
from homeassistant.helpers.rascalscheduler import get_routine_id


class ActionTimeRange:
    """Maintains the start and end times of an action."""

    def __init__(self, start_time: datetime) -> None:
        """Initialize the action's time range."""
        self.start_time = start_time
        self.end_time: datetime | None = None

    def end(self, end_time: datetime) -> None:
        """Set the end time of the action."""
        self.end_time = end_time

    def idle_time(self, prev: "ActionTimeRange") -> timedelta:
        """Calculate the idle time between this action and the previous action."""
        if not prev.end_time:
            raise ValueError("Previous action has not ended.")
        return self.start_time - prev.end_time


class ScheduleMetrics:
    """Maintains a schedule's information and metrics."""

    def __init__(
        self,
        rescheduling_policy: Optional[str] = None,
        result_dir: Optional[str] = None,
        sm: Optional["ScheduleMetrics"] = None,
    ) -> None:
        """Initialize the schedule's metrics.

        Args:
            rescheduling_policy: The rescheduling policy used in the schedule.
            result_dir: The directory to save the schedule metrics.
            sm: A `ScheduleMetrics` object to copy from.
        """
        if rescheduling_policy and result_dir:
            self._rescheduling_policy = rescheduling_policy
            self._result_dir = result_dir
            self._version = 0
            self._arrival_times = dict[str, datetime]()
            self._remaining_actions = dict[str, set[str]]()
            self._start_times = dict[str, datetime]()
            self._end_times = dict[str, datetime]()
            self._wait_times = dict[str, timedelta]()
            self._exec_times = dict[str, timedelta]()
            self._first_arrival_time: Optional[datetime] = None
            self._schedule_start: Optional[datetime] = None
            self._schedule_end: Optional[datetime] = None
            self._action_times = dict[str, dict[str, ActionTimeRange]]()
            self._last_action_end = dict[str, Optional[datetime]]()
            self._idle_times = dict[str, timedelta]()
            self._parallelism = dict[datetime, int]()
        elif sm:
            self._rescheduling_policy = sm._rescheduling_policy
            self._result_dir = sm._result_dir
            self._version = sm._version
            self._arrival_times = copy.deepcopy(sm._arrival_times)
            self._remaining_actions = copy.deepcopy(sm._remaining_actions)
            self._start_times = copy.deepcopy(sm._start_times)
            self._end_times = copy.deepcopy(sm._end_times)
            self._wait_times = copy.deepcopy(sm._wait_times)
            self._exec_times = copy.deepcopy(sm._exec_times)
            self._first_arrival_time = sm._first_arrival_time
            self._schedule_start = sm._schedule_start
            self._schedule_end = sm._schedule_end
            self._action_times = copy.deepcopy(sm._action_times)
            self._last_action_end = copy.deepcopy(sm._last_action_end)
            self._idle_times = copy.deepcopy(sm._idle_times)
            self._parallelism = copy.deepcopy(sm._parallelism)

    def set_rescheduling_policy(self, rescheduling_policy: str) -> None:
        """Set the rescheduling policy if not already set.

        Args:
            rescheduling_policy: The rescheduling policy to set.

        """
        self._rescheduling_policy = rescheduling_policy

    def record_routine_arrival(
        self, routine_id: str, arrival_time: datetime, action_ids: set[str]
    ) -> None:
        """Record the arrival time of a routine.

        Args:
            routine_id: The ID of the routine.
            arrival_time: The arrival time of the routine.
            action_ids: The set of action IDs associated with the routine.

        Raises:
            ValueError: If the routine has already arrived.

        """
        if routine_id in self._arrival_times:
            raise ValueError(f"Routine {routine_id} has already arrived.")
        arrival_time = arrival_time.replace(tzinfo=None)
        self._arrival_times[routine_id] = arrival_time
        if not self._first_arrival_time:
            self._first_arrival_time = arrival_time

        self._remaining_actions[routine_id] = action_ids

    def _record_routine_start(self, action_id: str, start_time: datetime) -> None:
        """Record the start time of a routine.

        Args:
            action_id: The ID of the routine's action.
            start_time: The start time of the routine.

        Raises:
            ValueError: If the routine has not arrived.

        """
        routine_id = get_routine_id(action_id)
        if (
            routine_id not in self._start_times
            or start_time < self._start_times[routine_id]
        ):
            self._start_times[routine_id] = start_time
            if routine_id not in self._remaining_actions:
                raise ValueError(f"Routine {routine_id} has not arrived.")
            if action_id in self._remaining_actions[routine_id]:
                self._remaining_actions[routine_id].remove(action_id)

            if not self._schedule_start or start_time < self._schedule_start:
                self._schedule_start = start_time

    def _record_routine_end(self, action_id: str, end_time: datetime) -> None:
        """Record the end time of a routine.

        Args:
            action_id: The ID of the routine's action.
            end_time: The end time of the routine.

        Raises:
            ValueError: If the routine has not arrived.

        """
        routine_id = get_routine_id(action_id)
        if routine_id not in self._end_times or end_time > self._end_times[routine_id]:
            self._end_times[routine_id] = end_time
            if routine_id not in self._remaining_actions:
                raise ValueError(f"Routine {routine_id} has not arrived.")
            if not self._schedule_end or end_time > self._schedule_end:
                self._schedule_end = end_time
            if self._remaining_actions[routine_id]:
                return
            # all actions of the routine have been executed
            del self._remaining_actions[routine_id]
            self._wait_times[routine_id] = (
                self._start_times[routine_id] - self._arrival_times[routine_id]
            )
            del self._arrival_times[routine_id]
            self._exec_times[routine_id] = end_time - self._start_times[routine_id]
            del self._start_times[routine_id]

    def record_action_start(
        self, time: datetime, entity_id: str, action_id: str
    ) -> None:
        """Record the start of an action. Called by the scheduler while executing.

        Args:
            time: The time of the action start.
            entity_id: The ID of the entity associated with the action.
            action_id: The ID of the action.

        """
        time = time.replace(tzinfo=None)

        # dict should be ordered by insertion time in Python 3.7+
        last_parallelism = (
            list(self._parallelism.values())[-1] if self._parallelism else 0
        )

        # parallelism increase
        self._parallelism[time] = last_parallelism + 1

        # idle time calculation
        if entity_id in self._last_action_end:
            if entity_id not in self._idle_times:
                self._idle_times[entity_id] = timedelta(0)
            last_action_end = self._last_action_end[entity_id]
            if last_action_end:
                # this might be wrong, if actions are not scheduled in order
                self._idle_times[entity_id] += time - last_action_end
        self._last_action_end[entity_id] = None

        # routine start
        self._record_routine_start(action_id, time)

    def record_action_end(self, time: datetime, entity_id: str, action_id: str) -> None:
        """Record the end of an action. Called by the scheduler while executing.

        Args:
            time: The time of the action end.
            entity_id: The ID of the entity associated with the action.
            action_id: The ID of the action.

        """
        time = time.replace(tzinfo=None)

        # dict should be ordered by insertion time in Python 3.7+
        last_parallelism = (
            list(self._parallelism.values())[-1] if self._parallelism else 0
        )

        # parallelism decrease
        self._parallelism[time] = last_parallelism - 1

        # idle time calculation preparation
        self._last_action_end[entity_id] = time

        # routine end
        self._record_routine_end(action_id, time)

    def record_scheduled_action_start(
        self, time: datetime, entity_id: str, action_id: str
    ) -> None:
        """Record the start of a scheduled action. Called by the optimal rescheduler."""
        if entity_id not in self._action_times:
            self._action_times[entity_id] = dict[str, ActionTimeRange]()

        time = time.replace(tzinfo=None)
        self._action_times[entity_id][action_id] = ActionTimeRange(time)

        # routine start
        self._record_routine_start(action_id, time)

    def record_scheduled_action_end(
        self, time: datetime, entity_id: str, action_id: str
    ) -> None:
        """Record the end of a scheduled action. Called by the optimal rescheduler."""
        if entity_id not in self._action_times:
            raise ValueError(f"Entity {entity_id} has no scheduled actions.")
        if action_id not in self._action_times[entity_id]:
            raise ValueError(
                f"Action {action_id} has not started on entity {entity_id}."
            )
        time = time.replace(tzinfo=None)
        self._action_times[entity_id][action_id].end(time)

        # routine end
        self._record_routine_end(action_id, time)

    @property
    def schedule_length(self) -> timedelta:
        """Calculate the schedule's length.

        Returns:
            The length of the schedule as a `timedelta` object.

        Raises:
            ValueError: If the schedule has not started or ended.

        """
        if not self._schedule_start or not self._schedule_end:
            raise ValueError("Schedule has not started or ended.")
        return self._schedule_end - self._schedule_start

    @property
    def wait_times(self) -> dict[str, timedelta]:
        """Return the wait times of the routines.

        Returns:
            A dictionary mapping routine IDs to their wait times as `timedelta` objects.

        """
        return self._wait_times

    @property
    def avg_wait_time(self) -> timedelta:
        """Return the average wait time of the routines.

        Returns:
            The average wait time as a `timedelta` object.

        """
        if not self._wait_times:
            return timedelta(0)
        return sum(self._wait_times.values(), timedelta(0)) / len(self._wait_times)

    @property
    def p95_wait_time(self) -> timedelta:
        """Return the 95th percentile wait time of the routines.

        Returns:
            The 95th percentile wait time as a `timedelta` object.

        """
        wait_times = list(self._wait_times.values())
        wait_times.sort()
        return wait_times[int(len(wait_times) * 0.95)]

    @property
    def exec_times(self) -> dict[str, timedelta]:
        """Return the execution times of the routines.

        Returns:
            A dictionary mapping routine IDs to their execution times as `timedelta` objects.

        """
        return self._exec_times

    @property
    def exec_time_std_dev(self) -> float:
        """Return the standard deviation of the execution times of the routines.

        Returns:
            The standard deviation of the execution times as a `timedelta` object.

        """
        if not self._exec_times:
            return 0.0
        avg_exec_time = sum(self._exec_times.values(), timedelta(0)) / len(
            self._exec_times
        )
        return sum(
            (exec_time - avg_exec_time).total_seconds() ** 2
            for exec_time in self._exec_times.values()
        ) / len(self._exec_times)

    @property
    def latencies(self) -> dict[str, timedelta]:
        """Return the latencies of the routines.

        Returns:
            A dictionary mapping routine IDs to their latencies as `timedelta` objects.

        """
        latencies = dict[str, timedelta]()
        for rtn_id, exec_time in self._exec_times.items():
            latencies[rtn_id] = self._wait_times[rtn_id] + exec_time
        return latencies

    @property
    def avg_latency(self) -> timedelta:
        """Return the average latency of the routines.

        Returns:
            The average latency as a `timedelta` object.

        """
        if not self.latencies:
            return timedelta(0)
        return sum(self.latencies.values(), timedelta(0)) / len(self.latencies)

    @property
    def p95_latency(self) -> timedelta:
        """Return the 95th percentile latency of the routines.

        Returns:
            The 95th percentile latency as a `timedelta` object.

        """
        latencies = list(self.latencies.values())
        latencies.sort()
        return latencies[int(len(latencies) * 0.95)]

    @property
    def idle_times(self) -> dict[str, timedelta]:
        """Return the idle times of the entities.

        Returns:
            A dictionary mapping entity IDs to their idle times as `timedelta` objects.

        """
        for entity_id, actions in self._action_times.items():
            sorted_actions = sorted(actions.values(), key=lambda x: x.start_time)
            last_action_end = None
            if self._last_action_end[entity_id]:
                last_action_end = self._last_action_end[entity_id]
            if entity_id not in self._idle_times:
                self._idle_times[entity_id] = timedelta(0)
            for action in sorted_actions:
                if last_action_end:
                    self._idle_times[entity_id] += action.start_time - last_action_end
                last_action_end = action.end_time

        return self._idle_times

    @property
    def avg_idle_time(self) -> timedelta:
        """Return the average idle time of the entities.

        Returns:
            The average idle time as a `timedelta` object.

        """
        if not self._idle_times:
            return timedelta(0)
        return sum(self._idle_times.values(), timedelta(0)) / len(self._idle_times)

    @property
    def p95_idle_time(self) -> timedelta:
        """Return the 95th percentile idle time of the entities.

        Returns:
            The 95th percentile idle time as a `timedelta` object.

        """
        idle_times = list(self._idle_times.values())
        idle_times.sort()
        return idle_times[int(len(idle_times) * 0.95)]

    @property
    def parallelism(self) -> dict[datetime, int]:
        """Return the parallelism of the routines.

        Returns:
            A dictionary mapping timestamps to the parallelism value at that time.

        """
        # sort action events across all entities
        global_action_timeline = dict[datetime, tuple[str, bool]]()
        for action_id, actions in self._action_times.items():
            sorted_actions = sorted(actions.values(), key=lambda x: x.start_time)
            for action in sorted_actions:
                global_action_timeline[action.start_time] = (action_id, True)
                if not action.end_time:
                    raise ValueError(f"Action {action_id} has not ended.")
                global_action_timeline[action.end_time] = (action_id, False)
        global_action_timeline = dict(sorted(global_action_timeline.items()))

        # calculate parallelism
        for event_time, (_, is_start) in global_action_timeline.items():
            if is_start:
                if event_time not in self._parallelism:
                    self._parallelism[event_time] = 0
                self._parallelism[event_time] += 1
            else:
                self._parallelism[event_time] -= 1

        return self._parallelism

    @property
    def avg_parallelism(self) -> float:
        """Return the average parallelism of the schedule.

        Returns:
            The average parallelism as a float.

        """
        if not self._parallelism:
            return 0.0
        return sum(self._parallelism.values()) / len(self._parallelism)

    @property
    def p05_parallelism(self) -> float:
        """Return the 5th percentile parallelism of the schedule.

        Returns:
            The 5th percentile parallelism as an integer.

        """
        if not self._parallelism:
            return 0.0
        parallelism = list(self._parallelism.values())
        parallelism.sort()
        return parallelism[int(len(parallelism) * 0.95)]

    def get(self, metric: str) -> float:
        """Return the schedule metric of interest."""
        if metric == MIN_LENGTH:
            return self.schedule_length.total_seconds()
        if metric == MIN_AVG_RTN_WAIT_TIME:
            return self.avg_wait_time.total_seconds()
        if metric == MIN_P95_RTN_WAIT_TIME:
            return self.p95_wait_time.total_seconds()
        if metric == MIN_RTN_EXEC_TIME_STD_DEV:
            return self.exec_time_std_dev
        if metric == MIN_AVG_RTN_LATENCY:
            return self.avg_latency.total_seconds()
        if metric == MIN_P95_RTN_LATENCY:
            return self.p95_latency.total_seconds()
        if metric == MIN_AVG_IDLE_TIME:
            return self.avg_idle_time.total_seconds()
        if metric == MIN_P95_IDLE_TIME:
            return self.p95_idle_time.total_seconds()
        if metric == MAX_AVG_PARALLELISM:
            return self.avg_parallelism
        if metric == MAX_P05_PARALLELISM:
            return self.p05_parallelism
        raise ValueError(f"Metric {metric} is not supported.")

    def save_metrics(self, final: bool = False) -> None:
        """Save the schedule metrics to a file."""
        self._version += 1
        if final:
            filename = "schedule_metrics"
        else:
            filename = f"{self._rescheduling_policy}_metrics_{self._version}"
        with open(f"{self._result_dir}/{filename}.txt", "w", encoding="utf-8") as f:
            f.write(f"Schedule Length: {self.schedule_length}\n")
            f.write(f"Average Wait Time: {self.avg_wait_time}\n")
            f.write(f"95th Percentile Wait Time: {self.p95_wait_time}\n")
            f.write(f"Average Latency: {self.avg_latency}\n")
            f.write(f"95th Percentile Latency: {self.p95_latency}\n")
            f.write(f"Average Idle Time: {self.avg_idle_time}\n")
            f.write(f"95th Percentile Idle Time: {self.p95_idle_time}\n")
            f.write(f"Average Parallelism: {self.avg_parallelism}\n")
            f.write(f"5th Percentile Parallelism: {self.p05_parallelism}\n")

    def remove_action_times(self) -> None:
        """Remove the action times of all entities."""
        for entity_id in self._action_times:
            del self._action_times[entity_id]
