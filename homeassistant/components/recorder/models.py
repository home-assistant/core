"""Models for SQLAlchemy."""
import json
import logging

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    distinct,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session

from homeassistant.const import MAX_LENGTH_EVENT_TYPE
from homeassistant.core import Context, Event, EventOrigin, State, split_entity_id
from homeassistant.helpers.json import JSONEncoder
import homeassistant.util.dt as dt_util

# SQLAlchemy Schema
# pylint: disable=invalid-name
Base = declarative_base()

SCHEMA_VERSION = 14

_LOGGER = logging.getLogger(__name__)

DB_TIMEZONE = "+00:00"

TABLE_EVENTS = "events"
TABLE_STATES = "states"
TABLE_RECORDER_RUNS = "recorder_runs"
TABLE_SCHEMA_CHANGES = "schema_changes"

ALL_TABLES = [TABLE_STATES, TABLE_EVENTS, TABLE_RECORDER_RUNS, TABLE_SCHEMA_CHANGES]

DATETIME_TYPE = DateTime(timezone=True).with_variant(
    mysql.DATETIME(timezone=True, fsp=6), "mysql"
)


class Events(Base):  # type: ignore
    """Event history data."""

    __table_args__ = {
        "mysql_default_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    __tablename__ = TABLE_EVENTS
    event_id = Column(Integer, Identity(), primary_key=True)
    event_type = Column(String(MAX_LENGTH_EVENT_TYPE))
    event_data = Column(Text().with_variant(mysql.LONGTEXT, "mysql"))
    origin = Column(String(32))
    time_fired = Column(DATETIME_TYPE, index=True)
    created = Column(DATETIME_TYPE, default=dt_util.utcnow)
    context_id = Column(String(36), index=True)
    context_user_id = Column(String(36), index=True)
    context_parent_id = Column(String(36), index=True)

    __table_args__ = (
        # Used for fetching events at a specific time
        # see logbook
        Index("ix_events_event_type_time_fired", "event_type", "time_fired"),
    )

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.Events("
            f"id={self.event_id}, type='{self.event_type}', data='{self.event_data}', "
            f"origin='{self.origin}', time_fired='{self.time_fired}'"
            f")>"
        )

    @staticmethod
    def from_event(event, event_data=None):
        """Create an event database object from a native event."""
        return Events(
            event_type=event.event_type,
            event_data=event_data or json.dumps(event.data, cls=JSONEncoder),
            origin=str(event.origin.value),
            time_fired=event.time_fired,
            context_id=event.context.id,
            context_user_id=event.context.user_id,
            context_parent_id=event.context.parent_id,
        )

    def to_native(self, validate_entity_id=True):
        """Convert to a natve HA Event."""
        context = Context(
            id=self.context_id,
            user_id=self.context_user_id,
            parent_id=self.context_parent_id,
        )
        try:
            return Event(
                self.event_type,
                json.loads(self.event_data),
                EventOrigin(self.origin),
                process_timestamp(self.time_fired),
                context=context,
            )
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting to event: %s", self)
            return None


class States(Base):  # type: ignore
    """State change history."""

    __table_args__ = {
        "mysql_default_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    __tablename__ = TABLE_STATES
    state_id = Column(Integer, Identity(), primary_key=True)
    domain = Column(String(64))
    entity_id = Column(String(255))
    state = Column(String(255))
    attributes = Column(Text().with_variant(mysql.LONGTEXT, "mysql"))
    event_id = Column(
        Integer, ForeignKey("events.event_id", ondelete="CASCADE"), index=True
    )
    last_changed = Column(DATETIME_TYPE, default=dt_util.utcnow)
    last_updated = Column(DATETIME_TYPE, default=dt_util.utcnow, index=True)
    created = Column(DATETIME_TYPE, default=dt_util.utcnow)
    old_state_id = Column(Integer, ForeignKey("states.state_id"), index=True)
    event = relationship("Events", uselist=False)
    old_state = relationship("States", remote_side=[state_id])

    __table_args__ = (
        # Used for fetching the state of entities at a specific time
        # (get_states in history.py)
        Index("ix_states_entity_id_last_updated", "entity_id", "last_updated"),
    )

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.States("
            f"id={self.state_id}, domain='{self.domain}', entity_id='{self.entity_id}', "
            f"state='{self.state}', event_id='{self.event_id}', "
            f"last_updated='{self.last_updated.isoformat(sep=' ', timespec='seconds')}', "
            f"old_state_id={self.old_state_id}"
            f")>"
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

    def to_native(self, validate_entity_id=True):
        """Convert to an HA state object."""
        try:
            return State(
                self.entity_id,
                self.state,
                json.loads(self.attributes),
                process_timestamp(self.last_changed),
                process_timestamp(self.last_updated),
                # Join the events table on event_id to get the context instead
                # as it will always be there for state_changed events
                context=Context(id=None),
                validate_entity_id=validate_entity_id,
            )
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting row to state: %s", self)
            return None


class RecorderRuns(Base):  # type: ignore
    """Representation of recorder run."""

    __tablename__ = TABLE_RECORDER_RUNS
    run_id = Column(Integer, Identity(), primary_key=True)
    start = Column(DateTime(timezone=True), default=dt_util.utcnow)
    end = Column(DateTime(timezone=True))
    closed_incorrect = Column(Boolean, default=False)
    created = Column(DateTime(timezone=True), default=dt_util.utcnow)

    __table_args__ = (Index("ix_recorder_runs_start_end", "start", "end"),)

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        end = (
            f"'{self.end.isoformat(sep=' ', timespec='seconds')}'" if self.end else None
        )
        return (
            f"<recorder.RecorderRuns("
            f"id={self.run_id}, start='{self.start.isoformat(sep=' ', timespec='seconds')}', "
            f"end={end}, closed_incorrect={self.closed_incorrect}, "
            f"created='{self.created.isoformat(sep=' ', timespec='seconds')}'"
            f")>"
        )

    def entity_ids(self, point_in_time=None):
        """Return the entity ids that existed in this run.

        Specify point_in_time if you want to know which existed at that point
        in time inside the run.
        """
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

    def to_native(self, validate_entity_id=True):
        """Return self, native format is this model."""
        return self


class SchemaChanges(Base):  # type: ignore
    """Representation of schema version changes."""

    __tablename__ = TABLE_SCHEMA_CHANGES
    change_id = Column(Integer, Identity(), primary_key=True)
    schema_version = Column(Integer)
    changed = Column(DateTime(timezone=True), default=dt_util.utcnow)

    def __repr__(self) -> str:
        """Return string representation of instance for debugging."""
        return (
            f"<recorder.SchemaChanges("
            f"id={self.change_id}, schema_version={self.schema_version}, "
            f"changed='{self.changed.isoformat(sep=' ', timespec='seconds')}'"
            f")>"
        )


def process_timestamp(ts):
    """Process a timestamp into datetime object."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=dt_util.UTC)

    return dt_util.as_utc(ts)


def process_timestamp_to_utc_isoformat(ts):
    """Process a timestamp into UTC isotime."""
    if ts is None:
        return None
    if ts.tzinfo == dt_util.UTC:
        return ts.isoformat()
    if ts.tzinfo is None:
        return f"{ts.isoformat()}{DB_TIMEZONE}"
    return ts.astimezone(dt_util.UTC).isoformat()
