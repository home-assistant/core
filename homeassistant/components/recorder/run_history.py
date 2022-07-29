"""Track recorder run history."""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm.session import Session

import homeassistant.util.dt as dt_util

from .db_schema import RecorderRuns
from .models import process_timestamp


def _find_recorder_run_for_start_time(
    run_history: _RecorderRunsHistory, start: datetime
) -> RecorderRuns | None:
    """Find the recorder run for a start time in _RecorderRunsHistory."""
    run_timestamps = run_history.run_timestamps
    runs_by_timestamp = run_history.runs_by_timestamp

    # bisect_left tells us were we would insert
    # a value in the list of runs after the start timestamp.
    #
    # The run before that (idx-1) is when the run started
    #
    # If idx is 0, history never ran before the start timestamp
    #
    if idx := bisect.bisect_left(run_timestamps, start.timestamp()):
        return runs_by_timestamp[run_timestamps[idx - 1]]
    return None


@dataclass(frozen=True)
class _RecorderRunsHistory:
    """Bisectable history of RecorderRuns."""

    run_timestamps: list[int]
    runs_by_timestamp: dict[int, RecorderRuns]


class RunHistory:
    """Track recorder run history."""

    def __init__(self) -> None:
        """Track recorder run history."""
        self._recording_start = dt_util.utcnow()
        self._current_run_info: RecorderRuns | None = None
        self._run_history = _RecorderRunsHistory([], {})

    @property
    def recording_start(self) -> datetime:
        """Return the time the recorder started recording states."""
        return self._recording_start

    @property
    def first(self) -> RecorderRuns:
        """Get the first run."""
        if runs_by_timestamp := self._run_history.runs_by_timestamp:
            return next(iter(runs_by_timestamp.values()))
        return self.current

    @property
    def current(self) -> RecorderRuns:
        """Get the current run."""
        assert self._current_run_info is not None
        return self._current_run_info

    def get(self, start: datetime) -> RecorderRuns | None:
        """Return the recorder run that started before or at start.

        If the first run started after the start, return None
        """
        if start >= self.recording_start:
            return self.current
        return _find_recorder_run_for_start_time(self._run_history, start)

    def start(self, session: Session) -> None:
        """Start a new run.

        Must run in the recorder thread.
        """
        self._current_run_info = RecorderRuns(
            start=self.recording_start, created=dt_util.utcnow()
        )
        session.add(self._current_run_info)
        session.flush()
        session.expunge(self._current_run_info)
        self.load_from_db(session)

    def reset(self) -> None:
        """Reset the run when the database is changed or fails.

        Must run in the recorder thread.
        """
        self._recording_start = dt_util.utcnow()
        self._current_run_info = None

    def end(self, session: Session) -> None:
        """End the current run.

        Must run in the recorder thread.
        """
        assert self._current_run_info is not None
        self._current_run_info.end = dt_util.utcnow()
        session.add(self._current_run_info)

    def load_from_db(self, session: Session) -> None:
        """Update the run cache.

        Must run in the recorder thread.
        """
        run_timestamps: list[int] = []
        runs_by_timestamp: dict[int, RecorderRuns] = {}

        for run in session.query(RecorderRuns).order_by(RecorderRuns.start.asc()).all():
            session.expunge(run)
            if run_dt := process_timestamp(run.start):
                timestamp = run_dt.timestamp()
                run_timestamps.append(timestamp)
                runs_by_timestamp[timestamp] = run

        #
        # self._run_history is accessed in get()
        # which is allowed to be called from any thread
        #
        # We use a dataclass to ensure that when we update
        # run_timestamps and runs_by_timestamp
        # are never out of sync with each other.
        #
        self._run_history = _RecorderRunsHistory(run_timestamps, runs_by_timestamp)

    def clear(self) -> None:
        """Clear the current run after ending it.

        Must run in the recorder thread.
        """
        assert self._current_run_info is not None
        assert self._current_run_info.end is not None
        self._current_run_info = None
