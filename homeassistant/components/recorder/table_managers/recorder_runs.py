"""Track recorder run history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm.session import Session

from homeassistant.util import dt as dt_util

from ..db_schema import RecorderRuns


class RecorderRunsManager:
    """Track recorder run history."""

    def __init__(self) -> None:
        """Track recorder run history."""
        self._recording_start = dt_util.utcnow()
        self._current_run_info: RecorderRuns | None = None
        self._first_run: RecorderRuns | None = None

    @property
    def recording_start(self) -> datetime:
        """Return the time the recorder started recording states."""
        return self._recording_start

    @property
    def first(self) -> RecorderRuns:
        """Get the first run."""
        return self._first_run or self.current

    @property
    def current(self) -> RecorderRuns:
        """Get the current run."""
        # If start has not been called yet because the recorder is
        # still starting up we want history to use the current time
        # as the created time to ensure we can still return results
        # and we do not try to pull data from the previous run.
        return self._current_run_info or RecorderRuns(
            start=self.recording_start, created=dt_util.utcnow()
        )

    @property
    def active(self) -> bool:
        """Return if a run is active."""
        return self._current_run_info is not None

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
        if (
            run := session.query(RecorderRuns)
            .order_by(RecorderRuns.start.asc())
            .first()
        ):
            session.expunge(run)
        self._first_run = run

    def clear(self) -> None:
        """Clear the current run after ending it.

        Must run in the recorder thread.
        """
        self._current_run_info = None
