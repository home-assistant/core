"""Purge old data helper."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from itertools import zip_longest
import logging
from typing import TYPE_CHECKING, Final

from sqlalchemy import func, lambda_stmt, select, union_all
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import distinct
from sqlalchemy.sql.lambdas import StatementLambdaElement

from homeassistant.const import EVENT_STATE_CHANGED

from .const import MAX_ROWS_TO_PURGE
from .models import (
    Events,
    RecorderRuns,
    StateAttributes,
    States,
    StatisticsRuns,
    StatisticsShortTerm,
)
from .repack import repack_database
from .util import retryable_database_job, session_scope

if TYPE_CHECKING:
    from . import Recorder

_LOGGER = logging.getLogger(__name__)


@retryable_database_job("purge")
def purge_old_data(
    instance: Recorder, purge_before: datetime, repack: bool, apply_filter: bool = False
) -> bool:
    """Purge events and states older than purge_before.

    Cleans up an timeframe of an hour, based on the oldest record.
    """
    _LOGGER.debug(
        "Purging states and events before target %s",
        purge_before.isoformat(sep=" ", timespec="seconds"),
    )
    using_sqlite = instance.using_sqlite()

    with session_scope(session=instance.get_session()) as session:  # type: ignore[misc]
        # Purge a max of MAX_ROWS_TO_PURGE, based on the oldest states or events record
        (
            event_ids,
            state_ids,
            attributes_ids,
        ) = _select_event_state_and_attributes_ids_to_purge(session, purge_before)
        statistics_runs = _select_statistics_runs_to_purge(session, purge_before)
        short_term_statistics = _select_short_term_statistics_to_purge(
            session, purge_before
        )

        if state_ids:
            _purge_state_ids(instance, session, state_ids)

        if unused_attribute_ids_set := _select_unused_attributes_ids(
            session, attributes_ids, using_sqlite
        ):
            _purge_attributes_ids(instance, session, unused_attribute_ids_set)

        if event_ids:
            _purge_event_ids(session, event_ids)

        if statistics_runs:
            _purge_statistics_runs(session, statistics_runs)

        if short_term_statistics:
            _purge_short_term_statistics(session, short_term_statistics)

        if event_ids or statistics_runs or short_term_statistics:
            # Return false, as we might not be done yet.
            _LOGGER.debug("Purging hasn't fully completed yet")
            return False

        if apply_filter and _purge_filtered_data(instance, session) is False:
            _LOGGER.debug("Cleanup filtered data hasn't fully completed yet")
            return False

        _purge_old_recorder_runs(instance, session, purge_before)
    if repack:
        repack_database(instance)
    return True


def _select_event_state_and_attributes_ids_to_purge(
    session: Session, purge_before: datetime
) -> tuple[set[int], set[int], set[int]]:
    """Return a list of event, state, and attribute ids to purge."""
    events = (
        session.query(Events.event_id, States.state_id, States.attributes_id)
        .outerjoin(States, Events.event_id == States.event_id)
        .filter(Events.time_fired < purge_before)
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    _LOGGER.debug("Selected %s event ids to remove", len(events))
    event_ids = set()
    state_ids = set()
    attributes_ids = set()
    for event in events:
        event_ids.add(event.event_id)
        if event.state_id:
            state_ids.add(event.state_id)
        if event.attributes_id:
            attributes_ids.add(event.attributes_id)
    return event_ids, state_ids, attributes_ids


STATE_ATTRS_ID: Final = States.attributes_id


def _generate_find_attr_lambda(
    attr1: int,
    attr2: int | None,
    attr3: int | None,
    attr4: int | None,
    attr5: int | None,
    attr6: int | None,
    attr7: int | None,
    attr8: int | None,
    attr9: int | None,
    attr10: int | None,
    attr11: int | None,
    attr12: int | None,
    attr13: int | None,
    attr14: int | None,
    attr15: int | None,
    attr16: int | None,
    attr17: int | None,
    attr18: int | None,
    attr19: int | None,
    attr20: int | None,
    attr21: int | None,
    attr22: int | None,
    attr23: int | None,
    attr24: int | None,
    attr25: int | None,
    attr26: int | None,
    attr27: int | None,
    attr28: int | None,
    attr29: int | None,
    attr30: int | None,
    attr31: int | None,
    attr32: int | None,
    attr33: int | None,
    attr34: int | None,
    attr35: int | None,
    attr36: int | None,
    attr37: int | None,
    attr38: int | None,
    attr39: int | None,
    attr40: int | None,
    attr41: int | None,
    attr42: int | None,
    attr43: int | None,
    attr44: int | None,
    attr45: int | None,
    attr46: int | None,
    attr47: int | None,
    attr48: int | None,
    attr49: int | None,
    attr50: int | None,
    attr51: int | None,
    attr52: int | None,
    attr53: int | None,
    attr54: int | None,
    attr55: int | None,
    attr56: int | None,
    attr57: int | None,
    attr58: int | None,
    attr59: int | None,
    attr60: int | None,
    attr61: int | None,
    attr62: int | None,
    attr63: int | None,
    attr64: int | None,
    attr65: int | None,
    attr66: int | None,
    attr67: int | None,
    attr68: int | None,
    attr69: int | None,
    attr70: int | None,
    attr71: int | None,
    attr72: int | None,
    attr73: int | None,
    attr74: int | None,
    attr75: int | None,
    attr76: int | None,
    attr77: int | None,
    attr78: int | None,
    attr79: int | None,
    attr80: int | None,
    attr81: int | None,
    attr82: int | None,
    attr83: int | None,
    attr84: int | None,
    attr85: int | None,
    attr86: int | None,
    attr87: int | None,
    attr88: int | None,
    attr89: int | None,
    attr90: int | None,
    attr91: int | None,
    attr92: int | None,
    attr93: int | None,
    attr94: int | None,
    attr95: int | None,
    attr96: int | None,
    attr97: int | None,
    attr98: int | None,
    attr99: int | None,
    attr100: int | None,
) -> StatementLambdaElement:
    """Generate the find attributes select only once."""
    return lambda_stmt(
        lambda: union_all(
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr1),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr2),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr3),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr4),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr5),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr6),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr7),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr8),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr9),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr10),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr11),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr12),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr13),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr14),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr15),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr16),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr17),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr18),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr19),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr20),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr21),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr22),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr23),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr24),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr25),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr26),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr27),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr28),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr29),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr30),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr31),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr32),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr33),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr34),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr35),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr36),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr37),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr38),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr39),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr40),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr41),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr42),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr43),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr44),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr45),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr46),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr47),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr48),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr49),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr50),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr51),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr52),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr53),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr54),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr55),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr56),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr57),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr58),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr59),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr60),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr61),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr62),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr63),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr64),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr65),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr66),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr67),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr68),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr69),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr70),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr71),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr72),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr73),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr74),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr75),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr76),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr77),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr78),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr79),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr80),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr81),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr82),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr83),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr84),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr85),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr86),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr87),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr88),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr89),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr90),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr91),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr92),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr93),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr94),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr95),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr96),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr97),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr98),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr99),
            select(func.min(STATE_ATTRS_ID)).where(STATE_ATTRS_ID == attr100),
        )
    )


def _select_unused_attributes_ids(
    session: Session, attributes_ids: set[int], using_sqlite: bool
) -> set[int]:
    """Return a set of attributes ids that are not used by any states in the database."""
    if not attributes_ids:
        return set()

    if using_sqlite:
        #
        # SQLite has a superior query optimizer for the distinct query below as it uses the
        # covering index without having to examine the rows directly for both of the queries
        # below.
        #
        # We use the distinct query for SQLite since the query in the other branch can
        # generate more than 500 unions which SQLite does not support.
        #
        # How MariaDB's query optimizer handles this query:
        # > explain select distinct attributes_id from states where attributes_id in (136723);
        # ...Using index
        #
        seen_ids = {
            state[0]
            for state in session.query(distinct(States.attributes_id))
            .filter(States.attributes_id.in_(attributes_ids))
            .all()
        }
    else:
        #
        # This branch is for DBMS that cannot optimize the distinct query well and has to examine
        # all the rows that match.
        #
        # This branch uses a union of simple queries, as each query is optimized away as the answer
        # to the query can be found in the index.
        #
        # The below query works for SQLite as long as there are no more than 500 attributes_id
        # to be selected. We currently do not have MySQL or PostgreSQL servers running in the
        # test suite; we test this path using SQLite when there are less than 500 attributes_id.
        #
        # How MariaDB's query optimizer handles this query:
        # > explain select min(attributes_id) from states where attributes_id = 136723;
        # ...Select tables optimized away
        #
        # We used to generate a query based on how many attribute_ids to find but
        # that meant sqlalchemy Transparent SQL Compilation Caching was working against
        # us by cached up to MAX_ROWS_TO_PURGE different statements.
        #
        # We now generate a single query and fill the attributes ids we do not need
        # with NULL values so sqlalchemy does not end up with MAX_ROWS_TO_PURGE
        # different queries in the cache.
        #
        seen_ids = set()
        groups = [iter(attributes_ids)] * 100
        for attr_ids in zip_longest(*groups, fillvalue=None):
            seen_ids |= {
                state[0]
                for state in session.execute(
                    _generate_find_attr_lambda(*attr_ids)
                ).all()
                if state[0] is not None
            }
    to_remove = attributes_ids - seen_ids
    _LOGGER.debug(
        "Selected %s shared attributes to remove",
        len(to_remove),
    )
    return to_remove


def _select_statistics_runs_to_purge(
    session: Session, purge_before: datetime
) -> list[int]:
    """Return a list of statistic runs to purge, but take care to keep the newest run."""
    statistic_runs = (
        session.query(StatisticsRuns.run_id)
        .filter(StatisticsRuns.start < purge_before)
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    statistic_runs_list = [run.run_id for run in statistic_runs]
    # Exclude the newest statistics run
    if (
        last_run := session.query(func.max(StatisticsRuns.run_id)).scalar()
    ) and last_run in statistic_runs_list:
        statistic_runs_list.remove(last_run)

    _LOGGER.debug("Selected %s statistic runs to remove", len(statistic_runs))
    return statistic_runs_list


def _select_short_term_statistics_to_purge(
    session: Session, purge_before: datetime
) -> list[int]:
    """Return a list of short term statistics to purge."""
    statistics = (
        session.query(StatisticsShortTerm.id)
        .filter(StatisticsShortTerm.start < purge_before)
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    _LOGGER.debug("Selected %s short term statistics to remove", len(statistics))
    return [statistic.id for statistic in statistics]


def _purge_state_ids(instance: Recorder, session: Session, state_ids: set[int]) -> None:
    """Disconnect states and delete by state id."""

    # Update old_state_id to NULL before deleting to ensure
    # the delete does not fail due to a foreign key constraint
    # since some databases (MSSQL) cannot do the ON DELETE SET NULL
    # for us.
    disconnected_rows = (
        session.query(States)
        .filter(States.old_state_id.in_(state_ids))
        .update({"old_state_id": None}, synchronize_session=False)
    )
    _LOGGER.debug("Updated %s states to remove old_state_id", disconnected_rows)

    deleted_rows = (
        session.query(States)
        .filter(States.state_id.in_(state_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s states", deleted_rows)

    # Evict eny entries in the old_states cache referring to a purged state
    _evict_purged_states_from_old_states_cache(instance, state_ids)


def _evict_purged_states_from_old_states_cache(
    instance: Recorder, purged_state_ids: set[int]
) -> None:
    """Evict purged states from the old states cache."""
    # Make a map from old_state_id to entity_id
    old_states = instance._old_states  # pylint: disable=protected-access
    old_state_reversed = {
        old_state.state_id: entity_id
        for entity_id, old_state in old_states.items()
        if old_state.state_id
    }

    # Evict any purged state from the old states cache
    for purged_state_id in purged_state_ids.intersection(old_state_reversed):
        old_states.pop(old_state_reversed[purged_state_id], None)


def _evict_purged_attributes_from_attributes_cache(
    instance: Recorder, purged_attributes_ids: set[int]
) -> None:
    """Evict purged attribute ids from the attribute ids cache."""
    # Make a map from attributes_id to the attributes json
    state_attributes_ids = (
        instance._state_attributes_ids  # pylint: disable=protected-access
    )
    state_attributes_ids_reversed = {
        attributes_id: attributes
        for attributes, attributes_id in state_attributes_ids.items()
    }

    # Evict any purged attributes from the state_attributes_ids cache
    for purged_attribute_id in purged_attributes_ids.intersection(
        state_attributes_ids_reversed
    ):
        state_attributes_ids.pop(
            state_attributes_ids_reversed[purged_attribute_id], None
        )


def _purge_attributes_ids(
    instance: Recorder, session: Session, attributes_ids: set[int]
) -> None:
    """Delete old attributes ids."""

    deleted_rows = (
        session.query(StateAttributes)
        .filter(StateAttributes.attributes_id.in_(attributes_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s attribute states", deleted_rows)

    # Evict any entries in the state_attributes_ids cache referring to a purged state
    _evict_purged_attributes_from_attributes_cache(instance, attributes_ids)


def _purge_statistics_runs(session: Session, statistics_runs: list[int]) -> None:
    """Delete by run_id."""
    deleted_rows = (
        session.query(StatisticsRuns)
        .filter(StatisticsRuns.run_id.in_(statistics_runs))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s statistic runs", deleted_rows)


def _purge_short_term_statistics(
    session: Session, short_term_statistics: list[int]
) -> None:
    """Delete by id."""
    deleted_rows = (
        session.query(StatisticsShortTerm)
        .filter(StatisticsShortTerm.id.in_(short_term_statistics))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s short term statistics", deleted_rows)


def _purge_event_ids(session: Session, event_ids: Iterable[int]) -> None:
    """Delete by event id."""
    deleted_rows = (
        session.query(Events)
        .filter(Events.event_id.in_(event_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s events", deleted_rows)


def _purge_old_recorder_runs(
    instance: Recorder, session: Session, purge_before: datetime
) -> None:
    """Purge all old recorder runs."""
    # Recorder runs is small, no need to batch run it
    deleted_rows = (
        session.query(RecorderRuns)
        .filter(RecorderRuns.start < purge_before)
        .filter(RecorderRuns.run_id != instance.run_history.current.run_id)
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s recorder_runs", deleted_rows)


def _purge_filtered_data(instance: Recorder, session: Session) -> bool:
    """Remove filtered states and events that shouldn't be in the database."""
    _LOGGER.debug("Cleanup filtered data")
    using_sqlite = instance.using_sqlite()

    # Check if excluded entity_ids are in database
    excluded_entity_ids: list[str] = [
        entity_id
        for (entity_id,) in session.query(distinct(States.entity_id)).all()
        if not instance.entity_filter(entity_id)
    ]
    if len(excluded_entity_ids) > 0:
        _purge_filtered_states(instance, session, excluded_entity_ids, using_sqlite)
        return False

    # Check if excluded event_types are in database
    excluded_event_types: list[str] = [
        event_type
        for (event_type,) in session.query(distinct(Events.event_type)).all()
        if event_type in instance.exclude_t
    ]
    if len(excluded_event_types) > 0:
        _purge_filtered_events(instance, session, excluded_event_types)
        return False

    return True


def _purge_filtered_states(
    instance: Recorder,
    session: Session,
    excluded_entity_ids: list[str],
    using_sqlite: bool,
) -> None:
    """Remove filtered states and linked events."""
    state_ids: list[int]
    attributes_ids: list[int]
    event_ids: list[int]
    state_ids, attributes_ids, event_ids = zip(
        *(
            session.query(States.state_id, States.attributes_id, States.event_id)
            .filter(States.entity_id.in_(excluded_entity_ids))
            .limit(MAX_ROWS_TO_PURGE)
            .all()
        )
    )
    event_ids = [id_ for id_ in event_ids if id_ is not None]
    _LOGGER.debug(
        "Selected %s state_ids to remove that should be filtered", len(state_ids)
    )
    _purge_state_ids(instance, session, set(state_ids))
    _purge_event_ids(session, event_ids)
    unused_attribute_ids_set = _select_unused_attributes_ids(
        session, {id_ for id_ in attributes_ids if id_ is not None}, using_sqlite
    )
    _purge_attributes_ids(instance, session, unused_attribute_ids_set)


def _purge_filtered_events(
    instance: Recorder, session: Session, excluded_event_types: list[str]
) -> None:
    """Remove filtered events and linked states."""
    events: list[Events] = (
        session.query(Events.event_id)
        .filter(Events.event_type.in_(excluded_event_types))
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    event_ids: list[int] = [
        event.event_id for event in events if event.event_id is not None
    ]
    _LOGGER.debug(
        "Selected %s event_ids to remove that should be filtered", len(event_ids)
    )
    states: list[States] = (
        session.query(States.state_id).filter(States.event_id.in_(event_ids)).all()
    )
    state_ids: set[int] = {state.state_id for state in states}
    _purge_state_ids(instance, session, state_ids)
    _purge_event_ids(session, event_ids)
    if EVENT_STATE_CHANGED in excluded_event_types:
        session.query(StateAttributes).delete(synchronize_session=False)
        instance._state_attributes_ids = {}  # pylint: disable=protected-access


@retryable_database_job("purge")
def purge_entity_data(instance: Recorder, entity_filter: Callable[[str], bool]) -> bool:
    """Purge states and events of specified entities."""
    using_sqlite = instance.using_sqlite()
    with session_scope(session=instance.get_session()) as session:  # type: ignore[misc]
        selected_entity_ids: list[str] = [
            entity_id
            for (entity_id,) in session.query(distinct(States.entity_id)).all()
            if entity_filter(entity_id)
        ]
        _LOGGER.debug("Purging entity data for %s", selected_entity_ids)
        if len(selected_entity_ids) > 0:
            # Purge a max of MAX_ROWS_TO_PURGE, based on the oldest states or events record
            _purge_filtered_states(instance, session, selected_entity_ids, using_sqlite)
            _LOGGER.debug("Purging entity data hasn't fully completed yet")
            return False

    return True
