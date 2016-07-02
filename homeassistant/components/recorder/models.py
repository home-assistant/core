"""Models for SQLAlchemy."""

import json
from datetime import datetime
import logging

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Index, Integer,
                        String, Text, distinct)
from sqlalchemy.ext.declarative import declarative_base
import homeassistant.util.dt as dt_util
from homeassistant.core import Event, EventOrigin, State
from homeassistant.remote import JSONEncoder

# SQLAlchemy Schema
# pylint: disable=invalid-name
Base = declarative_base()

_LOGGER = logging.getLogger(__name__)


class Events(Base):
    # pylint: disable=too-few-public-methods
    """Event history data."""

    __tablename__ = 'events'
    event_id = Column(Integer, primary_key=True)
    event_type = Column(String(32), index=True)
    event_data = Column(Text)
    origin = Column(String(32))
    time_fired = Column(DateTime(timezone=True))
    created = Column(DateTime(timezone=True), default=datetime.utcnow)

    @staticmethod
    def record_event(session, event):
        """Save an event to the database."""
        dbevent = Events(event_type=event.event_type,
                         event_data=json.dumps(event.data, cls=JSONEncoder),
                         origin=str(event.origin),
                         time_fired=event.time_fired)

        session.add(dbevent)
        session.commit()

        return dbevent.event_id

    def to_native(self):
        """Convert to a natve HA Event."""
        try:
            return Event(
                self.event_type,
                json.loads(self.event_data),
                EventOrigin(self.origin),
                dt_util.UTC.localize(self.time_fired)
            )
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting to event: %s", self)
            return None


class States(Base):
    # pylint: disable=too-few-public-methods
    """State change history."""

    __tablename__ = 'states'
    state_id = Column(Integer, primary_key=True)
    domain = Column(String(64))
    entity_id = Column(String(64))
    state = Column(String(255))
    attributes = Column(Text)
    origin = Column(String(32))
    event_id = Column(Integer, ForeignKey('events.event_id'))
    last_changed = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow)
    created = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (Index('states__state_changes',
                            'last_changed', 'last_updated', 'entity_id'),
                      Index('states__significant_changes',
                            'domain', 'last_updated', 'entity_id'), )

    @staticmethod
    def record_state(session, entity_id, state, event_id):
        """Save a state to the database."""
        now = dt_util.utcnow()

        dbstate = States(event_id=event_id, entity_id=entity_id)

        # State got deleted
        if state is None:
            dbstate.state = ''
            dbstate.domain = ''
            dbstate.attributes = '{}'
            dbstate.last_changed = now
            dbstate.last_updated = now
        else:
            dbstate.domain = state.domain
            dbstate.state = state.state
            dbstate.attributes = json.dumps(dict(state.attributes))
            dbstate.last_changed = state.last_changed
            dbstate.last_updated = state.last_updated

        session().add(dbstate)
        session().commit()

    def to_native(self):
        """Convert to an HA state object."""
        try:
            return State(
                self.entity_id, self.state,
                json.loads(self.attributes),
                dt_util.UTC.localize(self.last_changed),
                dt_util.UTC.localize(self.last_updated)
            )
        except ValueError:
            # When json.loads fails
            _LOGGER.exception("Error converting row to state: %s", self)
            return None


class RecorderRuns(Base):
    # pylint: disable=too-few-public-methods
    """Representation of recorder run."""

    __tablename__ = 'recorder_runs'
    run_id = Column(Integer, primary_key=True)
    start = Column(DateTime(timezone=True), default=datetime.utcnow)
    end = Column(DateTime(timezone=True))
    closed_incorrect = Column(Boolean, default=False)
    created = Column(DateTime(timezone=True), default=datetime.utcnow)

    def entity_ids(self, point_in_time=None):
        """Return the entity ids that existed in this run.

        Specify point_in_time if you want to know which existed at that point
        in time inside the run.
        """
        from homeassistant.components.recorder import Session, _verify_instance
        _verify_instance()

        query = Session().query(distinct(States.entity_id)).filter(
            States.created >= self.start)

        if point_in_time is not None or self.end is not None:
            query = query.filter(States.created < point_in_time)

        return [row.entity_id for row in query]

    def to_native(self):
        """Return self, native format is this model."""
        return self
