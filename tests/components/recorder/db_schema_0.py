"""Models for SQLAlchemy.

This file contains the original models definitions before schema tracking was
implemented. It is used to test the schema migration logic.
"""

import json
import logging

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    distinct,
)
from sqlalchemy.orm import declarative_base

from homeassistant.core import Event, EventOrigin, State, split_entity_id
from homeassistant.helpers.json import JSONEncoder
import homeassistant.util.dt as dt_util

# SQLAlchemy Schema
Base = declarative_base()

_LOGGER = logging.getLogger(__name__)


class Events(Base):  # type: ignore[valid-type,misc]
    """Event history data."""

    __tablename__ = "events"
    event_id = Column(Integer, primary_key=True)
    event_type = Column(String(32), index=True)
    event_data = Column(Text)
    origin = Column(String(32))
    time_fired = Column(DateTime(timezone=True))
    created = Column(DateTime(timezone=True), default=dt_util.utcnow)

    @staticmethod
    def from_event(event):
        """Create an event database object from a native event."""
        return Events(
            event_type=event.event_type,
            event_data=json.dumps(event.data, cls=JSONEncoder),
            origin=str(event.origin),
            time_fired=event.time_fired,
        )

    def to_native(self):
        """Convert to a natve HA Event."""
        try:
            return Event(
                self.event_type,
                json.loads(self.event_data),
                EventOrigin(self.origin),
                _process_timestamp(self.time_fired),
            )
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting to event: %s", self)
            return None


class States(Base):  # type: ignore[valid-type,misc]
    """State change history."""

    __tablename__ = "states"
    state_id = Column(Integer, primary_key=True)
    domain = Column(String(64))
    entity_id = Column(String(255))
    state = Column(String(255))
    attributes = Column(Text)
    event_id = Column(Integer, ForeignKey("events.event_id"))
    last_changed = Column(DateTime(timezone=True), default=dt_util.utcnow)
    last_updated = Column(DateTime(timezone=True), default=dt_util.utcnow)
    created = Column(DateTime(timezone=True), default=dt_util.utcnow)

    __table_args__ = (
        Index("states__state_changes", "last_changed", "last_updated", "entity_id"),
        Index("states__significant_changes", "domain", "last_updated", "entity_id"),
    )

    @staticmethod
    def from_event(event):
        """Create object from a state_changed event."""
        entity_id = event.data["entity_id"]
        state = event.data.get("new_state")

        dbstate = States(entity_id=entity_id)

        # State got deleted
        if state is None:
            dbstate.state = ""
            dbstate.domain = split_entity_id(entity_id)[0]
            dbstate.attributes = "{}"
            dbstate.last_changed = event.time_fired
            dbstate.last_updated = event.time_fired
        else:
            dbstate.domain = state.domain
            dbstate.state = state.state
            dbstate.attributes = json.dumps(dict(state.attributes), cls=JSONEncoder)
            dbstate.last_changed = state.last_changed
            dbstate.last_updated = state.last_updated

        return dbstate

    def to_native(self):
        """Convert to an HA state object."""
        try:
            return State(
                self.entity_id,
                self.state,
                json.loads(self.attributes),
                _process_timestamp(self.last_changed),
                _process_timestamp(self.last_updated),
            )
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting row to state: %s", self)
            return None


class RecorderRuns(Base):  # type: ignore[valid-type,misc]
    """Representation of recorder run."""

    __tablename__ = "recorder_runs"
    run_id = Column(Integer, primary_key=True)
    start = Column(DateTime(timezone=True), default=dt_util.utcnow)
    end = Column(DateTime(timezone=True))
    closed_incorrect = Column(Boolean, default=False)
    created = Column(DateTime(timezone=True), default=dt_util.utcnow)

    def entity_ids(self, point_in_time=None):
        """Return the entity ids that existed in this run.

        Specify point_in_time if you want to know which existed at that point
        in time inside the run.
        """
        from sqlalchemy.orm.session import Session

        session = Session.object_session(self)

        assert session is not None, "RecorderRuns need to be persisted"

        query = session.query(distinct(States.entity_id)).filter(
            States.last_updated >= self.start
        )

        if point_in_time is not None:
            query = query.filter(States.last_updated < point_in_time)
        elif self.end is not None:
            query = query.filter(States.last_updated < self.end)

        return [row[0] for row in query]

    def to_native(self):
        """Return self, native format is this model."""
        return self


def _process_timestamp(ts):
    """Process a timestamp into datetime object."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=dt_util.UTC)
    return dt_util.as_utc(ts)
