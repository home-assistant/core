"""Schedule metrics.

The `ScheduleMetrics` class is responsible for recording and calculating various metrics related to a schedule. It keeps track of arrival times, start times, end times, wait times, execution times, idle times, and parallelism of routines in a schedule.

Example usage:
    sm = ScheduleMetrics("FIFO", "results")
    sm.record_routine_arrival("routine1", datetime.now(), {"action1", "action2"})
    sm.record_action_start(datetime.now(), "entity1", "action1")
    sm.record_action_end(datetime.now(), "entity1", "action1")
    sm.record_scheduled_action_start(datetime.now(), "entity1", "action1")
    sm.record_scheduled_action_end(datetime.now(), "entity1", "action1")
    avg_wait_time = sm.avg_wait_time
    avg_latency = sm.avg_latency
    parallelism = sm.parallelism

"""

import copy
from datetime import datetime, timedelta
import logging
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
from homeassistant.helpers.rascalscheduler import datetime_to_string, get_routine_id

LOGGER = logging.getLogger("rasc.schedule_metrics")
LOGGER.setLevel(logging.DEBUG)


class ActionTimeRange:
    """Maintains the start and end times of an action."""

    def __init__(self, start_time: datetime) -> None:
        """Initialize the action's time range."""
        self.start_time = start_time
        self.end_time: datetime | None = None

    def __repr__(self) -> str:
        """Return the string representation of the action time range."""
        start_str = datetime_to_string(self.start_time)
        end_str = datetime_to_string(self.end_time) if self.end_time else "None"
        return f"ActionTimeRange(start_time={start_str}, end_time={end_str})"

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
            self._remaining_actions = dict[str, dict[str, list[str]]]()
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

    def __repr__(self) -> str:
        """Return the string representation of the schedule metrics."""
        arrival_times = {
            k: datetime_to_string(v) for k, v in self._arrival_times.items()
        }
        start_times = {k: datetime_to_string(v) for k, v in self._start_times.items()}
        end_times = {k: datetime_to_string(v) for k, v in self._end_times.items()}
        wait_times = {k: v.total_seconds() for k, v in self._wait_times.items()}
        exec_times = {k: v.total_seconds() for k, v in self._exec_times.items()}
        first_arrival_time = None
        if self._first_arrival_time:
            first_arrival_time = datetime_to_string(self._first_arrival_time)
        schedule_start = None
        if self._schedule_start:
            schedule_start = datetime_to_string(self._schedule_start)
        schedule_end = None
        if self._schedule_end:
            schedule_end = datetime_to_string(self._schedule_end)
        last_action_end = {
            k: datetime_to_string(v) if v else None
            for k, v in self._last_action_end.items()
        }
        idle_times = {k: v.total_seconds() for k, v in self._idle_times.items()}
        parallelism = {datetime_to_string(k): v for k, v in self.parallelism.items()}
        return (
            f"ScheduleMetrics(\n"
            f"rescheduling_policy={self._rescheduling_policy}, version={self._version},\n"
            f"arrival_times={arrival_times},\n"
            f"remaining_actions={self._remaining_actions},\n"
            f"start_times={start_times}, end_times={end_times},\n"
            f"wait_times={wait_times}, exec_times={exec_times},\n"
            f"first_arrival_time={first_arrival_time},\n"
            f"schedule_start={schedule_start},\n"
            f"schedule_end={schedule_end},\naction_times={self._action_times},\n"
            f"last_action_end={last_action_end},\nidle_times={idle_times},\n"
            f"parallelism={parallelism})"
        )

    def set_rescheduling_policy(self, rescheduling_policy: str) -> None:
        """Set the rescheduling policy if not already set.

        Args:
            rescheduling_policy: The rescheduling policy to set.

        """
        self._rescheduling_policy = rescheduling_policy

    def inc_version(self) -> None:
        """Increment the version number."""
        self._version += 1

    def record_routine_arrival(
        self,
        routine_id: str,
        arrival_time: datetime,
        sink_actions: dict[str, list[str]],
    ) -> None:
        """Record the arrival time of a routine.

        Args:
            routine_id: The ID of the routine.
            arrival_time: The arrival time of the routine.
            sink_actions: The mapping of sink action ids to target entities
              that the routine will execute.

        Raises:
            ValueError: If the routine has already arrived.

        """
        if routine_id in self._arrival_times:
            raise ValueError(f"Routine {routine_id} has already arrived.")
        arrival_time = arrival_time.replace(tzinfo=None)
        self._arrival_times[routine_id] = arrival_time
        if not self._first_arrival_time:
            self._first_arrival_time = arrival_time

        self._remaining_actions[routine_id] = sink_actions

    def _remove_routine_remaining_action(self, action_id: str, entity_id: str) -> None:
        routine_id = get_routine_id(action_id)
        if routine_id not in self._remaining_actions:
            raise ValueError(f"Routine {routine_id} has not arrived.")
        if action_id not in self._remaining_actions[routine_id]:
            return
        self._remaining_actions[routine_id][action_id].remove(entity_id)
        if not self._remaining_actions[routine_id][action_id]:
            del self._remaining_actions[routine_id][action_id]
        # LOGGER.debug("Action %s completed on entity %s", action_id, entity_id)
        # LOGGER.debug("New remaining actions for routine %s: %s", routine_id, self._remaining_actions[routine_id])

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

        self._remove_routine_remaining_action(action_id, entity_id)

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

        self._remove_routine_remaining_action(action_id, entity_id)

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
        if not self._schedule_start:
            raise ValueError("Schedule has not started: %s" % self)
        if not self._schedule_end:
            raise ValueError("Schedule has not ended: %s" % self)
        return self._schedule_end - self._schedule_start

    @property
    def wait_times(self) -> dict[str, timedelta]:
        """Return the wait times of the routines.

        Returns:
            A dictionary mapping routine IDs to their wait times as `timedelta` objects.

        """
        if not self._wait_times:
            LOGGER.warning("No wait times recorded")
        return self._wait_times

    @property
    def avg_wait_time(self) -> timedelta:
        """Return the average wait time of the routines.

        Returns:
            The average wait time as a `timedelta` object.

        """
        if not self._wait_times:
            LOGGER.warning("No wait times recorded")
            return timedelta(0)
        return sum(self._wait_times.values(), timedelta(0)) / len(self._wait_times)

    @property
    def p95_wait_time(self) -> timedelta:
        """Return the 95th percentile wait time of the routines.

        Returns:
            The 95th percentile wait time as a `timedelta` object.

        """
        if not self._wait_times:
            LOGGER.warning("No wait times recorded")
            return timedelta(0)
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
            LOGGER.warning("No exec times recorded")
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
        if not self._exec_times:
            LOGGER.warning("No exec times recorded")
            return latencies
        for rtn_id, exec_time in self._exec_times.items():
            if rtn_id not in self._wait_times:
                raise ValueError(f"Routine {rtn_id} has no wait time.")
            latencies[rtn_id] = self._wait_times[rtn_id] + exec_time
        return latencies

    @property
    def avg_latency(self) -> timedelta:
        """Return the average latency of the routines.

        Returns:
            The average latency as a `timedelta` object.

        """
        if not self.latencies:
            LOGGER.warning("No latencies recorded")
            return timedelta(0)
        return sum(self.latencies.values(), timedelta(0)) / len(self.latencies)

    @property
    def p95_latency(self) -> timedelta:
        """Return the 95th percentile latency of the routines.

        Returns:
            The 95th percentile latency as a `timedelta` object.

        """
        if not self.latencies:
            LOGGER.warning("No latencies recorded")
            return timedelta(0)
        latencies = list(self.latencies.values())
        latencies.sort()
        return latencies[int(len(latencies) * 0.95)]

    @property
    def idle_times(self) -> dict[str, timedelta]:
        """Return the idle times of the entities.

        Returns:
            A dictionary mapping entity IDs to their idle times as `timedelta` objects.

        """
        idle_times = copy.deepcopy(self._idle_times)
        for entity_id, actions in self._action_times.items():
            sorted_actions = sorted(actions.values(), key=lambda x: x.start_time)
            last_action_end = self._schedule_start
            if entity_id in self._last_action_end:
                last_action_end = self._last_action_end[entity_id]
            if entity_id not in idle_times:
                idle_times[entity_id] = timedelta(0)
            for action in sorted_actions:
                if last_action_end:
                    idle_times[entity_id] += action.start_time - last_action_end
                last_action_end = action.end_time
            if last_action_end and self._schedule_end:
                idle_times[entity_id] += self._schedule_end - last_action_end

        return idle_times

    @property
    def avg_idle_time(self) -> timedelta:
        """Return the average idle time of the entities.

        Returns:
            The average idle time as a `timedelta` object.

        """
        idle_times = list(self.idle_times.values())
        if not idle_times:
            LOGGER.warning("No idle times recorded")
            return timedelta(0)
        return sum(idle_times, timedelta(0)) / len(idle_times)

    @property
    def p95_idle_time(self) -> timedelta:
        """Return the 95th percentile idle time of the entities.

        Returns:
            The 95th percentile idle time as a `timedelta` object.

        """
        idle_times = list(self.idle_times.values())
        if not idle_times:
            LOGGER.warning("No idle times recorded")
            return timedelta(0)
        idle_times.sort()
        return idle_times[int(len(idle_times) * 0.95)]

    @property
    def parallelism(self) -> dict[datetime, int]:
        """Return the parallelism of the routines.

        Returns:
            A dictionary mapping timestamps to the parallelism value at that time.

        """
        # sort action events across all entities
        global_action_timeline = dict[datetime, list[tuple[str, bool]]]()
        for entity_id, actions in self._action_times.items():
            sorted_actions = sorted(actions.items(), key=lambda x: x[1].start_time)
            for action_id, action in sorted_actions:
                if action.start_time not in global_action_timeline:
                    global_action_timeline[action.start_time] = []
                global_action_timeline[action.start_time].append((entity_id, True))
                if not action.end_time:
                    raise ValueError(f"Action {action_id} has not ended.")
                if action.end_time not in global_action_timeline:
                    global_action_timeline[action.end_time] = []
                global_action_timeline[action.end_time].append((entity_id, False))
        global_action_timeline = dict(sorted(global_action_timeline.items()))

        # calculate parallelism
        parallelism = copy.deepcopy(self._parallelism)
        last_parallelism = list(parallelism.values())[-1] if parallelism else 0
        for event_time, events in global_action_timeline.items():
            for _, is_start in events:
                if is_start:
                    parallelism[event_time] = last_parallelism + 1
                else:
                    parallelism[event_time] = last_parallelism - 1
                last_parallelism = parallelism[event_time]

        return parallelism

    @property
    def avg_parallelism(self) -> float:
        """Return the average parallelism of the schedule.

        Returns:
            The average parallelism as a float.

        """
        if not self._parallelism:
            LOGGER.warning("No parallelism recorded")
            return 0.0

        schedule_length = self.schedule_length.total_seconds()

        parallelisms = self.parallelism
        last_time = None
        last_parallelism = None
        weighted_parallelism_sum = 0
        for time, parallelism in parallelisms.items():
            if last_time is None:
                last_time = time
                last_parallelism = parallelism
                continue
            if last_parallelism is None:
                raise ValueError("Last parallelism is None.")
            timediff = (time - last_time).total_seconds()
            weighted_parallelism_sum += timediff * last_parallelism
            last_time = time
            last_parallelism = parallelism

        return weighted_parallelism_sum / schedule_length

    @property
    def p05_parallelism(self) -> float:
        """Return the 5th percentile parallelism of the schedule.

        Returns:
            The 5th percentile parallelism as an integer.

        """
        if not self._parallelism:
            LOGGER.warning("No parallelism recorded")
            return 0.0

        schedule_length = self.schedule_length.total_seconds()

        parallelisms = self.parallelism
        last_time = None
        last_parallelism = None
        hist = dict[int, float]()
        for time, parallelism in parallelisms.items():
            if last_time is None:
                last_time = time
                last_parallelism = parallelism
                continue
            if last_parallelism is None:
                raise ValueError("Last parallelism is None.")
            timediff = (time - last_time).total_seconds()
            hist[last_parallelism] = hist.get(last_parallelism, 0) + timediff
            last_time = time
            last_parallelism = parallelism

        pdf = {k: v / schedule_length for k, v in hist.items()}
        cdf = dict[int, float]()
        cdf[0] = pdf.get(0, 0)
        for i in range(1, max(pdf.keys()) + 1):
            cdf[i] = cdf[i - 1] + pdf.get(i, 0)

        return min(cdf, key=lambda x: abs(cdf[x] - 0.05))

    def get(self, metric: str) -> float:
        """Return the schedule metric of interest."""
        timedelta_metrics = [
            MIN_LENGTH,
            MIN_AVG_RTN_WAIT_TIME,
            MIN_P95_RTN_WAIT_TIME,
            MIN_AVG_RTN_LATENCY,
            MIN_P95_RTN_LATENCY,
            MIN_AVG_IDLE_TIME,
            MIN_P95_IDLE_TIME,
        ]
        float_metrics = [
            MIN_RTN_EXEC_TIME_STD_DEV,
            MAX_AVG_PARALLELISM,
            MAX_P05_PARALLELISM,
        ]
        if metric in timedelta_metrics:
            result_timedelta: timedelta = getattr(self, metric)
            return result_timedelta.total_seconds()
        if metric in float_metrics:
            result_float: float = getattr(self, metric)
            return result_float

        raise ValueError(f"Metric {metric} is not supported.")

    def save_metrics(self, final: bool = False) -> None:
        """Save the schedule metrics to a file."""
        LOGGER.debug("Saving schedule metrics to file:\n%s", self)
        if final:
            filename = "schedule_metrics"
        else:
            filename = f"{self._rescheduling_policy}_metrics_{self._version}"
        with open(f"{self._result_dir}/{filename}.yaml", "w", encoding="utf-8") as f:
            f.write(f"Schedule Length: {self.schedule_length.total_seconds()}\n")
            f.write(f"Average Wait Time: {self.avg_wait_time.total_seconds()}\n")
            f.write(
                f"95th Percentile Wait Time: {self.p95_wait_time.total_seconds()}\n"
            )
            f.write(f"Average Latency: {self.avg_latency.total_seconds()}\n")
            f.write(f"95th Percentile Latency: {self.p95_latency.total_seconds()}\n")
            f.write(f"Average Idle Time: {self.avg_idle_time.total_seconds()}\n")
            f.write(
                f"95th Percentile Idle Time: {self.p95_idle_time.total_seconds()}\n"
            )
            f.write(f"Average Parallelism: {self.avg_parallelism}\n")
            f.write(f"5th Percentile Parallelism: {self.p05_parallelism}\n")

    def remove_action_times(self) -> None:
        """Remove the action times of all entities."""
        for entity_id in self._action_times:
            del self._action_times[entity_id]
