"""Purge old data helper."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from itertools import zip_longest
import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy.orm.session import Session

import homeassistant.util.dt as dt_util

from .const import SQLITE_MAX_BIND_VARS
from .db_schema import Events, States, StatesMeta
from .models import DatabaseEngine
from .queries import (
    attributes_ids_exist_in_states,
    attributes_ids_exist_in_states_with_fast_in_distinct,
    data_ids_exist_in_events,
    data_ids_exist_in_events_with_fast_in_distinct,
    delete_event_data_rows,
    delete_event_rows,
    delete_event_types_rows,
    delete_recorder_runs_rows,
    delete_states_attributes_rows,
    delete_states_meta_rows,
    delete_states_rows,
    delete_statistics_runs_rows,
    delete_statistics_short_term_rows,
    disconnect_states_rows,
    find_entity_ids_to_purge,
    find_event_types_to_purge,
    find_events_to_purge,
    find_latest_statistics_runs_run_id,
    find_legacy_event_state_and_attributes_and_data_ids_to_purge,
    find_legacy_row,
    find_short_term_statistics_to_purge,
    find_states_to_purge,
    find_statistics_runs_to_purge,
)
from .repack import repack_database
from .util import chunked, retryable_database_job, session_scope

if TYPE_CHECKING:
    from . import Recorder

_LOGGER = logging.getLogger(__name__)


DEFAULT_STATES_BATCHES_PER_PURGE = 20  # We expect ~95% de-dupe rate
DEFAULT_EVENTS_BATCHES_PER_PURGE = 15  # We expect ~92% de-dupe rate


@retryable_database_job("purge")
def purge_old_data(
    instance: Recorder,
    purge_before: datetime,
    repack: bool,
    apply_filter: bool = False,
    events_batch_size: int = DEFAULT_EVENTS_BATCHES_PER_PURGE,
    states_batch_size: int = DEFAULT_STATES_BATCHES_PER_PURGE,
) -> bool:
    """Purge events and states older than purge_before.

    Cleans up an timeframe of an hour, based on the oldest record.
    """
    _LOGGER.debug(
        "Purging states and events before target %s",
        purge_before.isoformat(sep=" ", timespec="seconds"),
    )
    with session_scope(session=instance.get_session()) as session:
        # Purge a max of SQLITE_MAX_BIND_VARS, based on the oldest states or events record
        has_more_to_purge = False
        if instance.use_legacy_events_index and _purging_legacy_format(session):
            _LOGGER.debug(
                "Purge running in legacy format as there are states with event_id"
                " remaining"
            )
            has_more_to_purge |= _purge_legacy_format(instance, session, purge_before)
        else:
            _LOGGER.debug(
                "Purge running in new format as there are NO states with event_id"
                " remaining"
            )
            # Once we are done purging legacy rows, we use the new method
            has_more_to_purge |= _purge_states_and_attributes_ids(
                instance, session, states_batch_size, purge_before
            )
            has_more_to_purge |= _purge_events_and_data_ids(
                instance, session, events_batch_size, purge_before
            )

        statistics_runs = _select_statistics_runs_to_purge(session, purge_before)
        short_term_statistics = _select_short_term_statistics_to_purge(
            session, purge_before
        )
        if statistics_runs:
            _purge_statistics_runs(session, statistics_runs)

        if short_term_statistics:
            _purge_short_term_statistics(session, short_term_statistics)

        if has_more_to_purge or statistics_runs or short_term_statistics:
            # Return false, as we might not be done yet.
            _LOGGER.debug("Purging hasn't fully completed yet")
            return False

        if apply_filter and _purge_filtered_data(instance, session) is False:
            _LOGGER.debug("Cleanup filtered data hasn't fully completed yet")
            return False

        # This purge cycle is finished, clean up old event types and
        # recorder runs
        if instance.event_type_manager.active:
            _purge_old_event_types(instance, session)

        if instance.states_meta_manager.active:
            _purge_old_entity_ids(instance, session)

        _purge_old_recorder_runs(instance, session, purge_before)
    if repack:
        repack_database(instance)
    return True


def _purging_legacy_format(session: Session) -> bool:
    """Check if there are any legacy event_id linked states rows remaining."""
    return bool(session.execute(find_legacy_row()).scalar())


def _purge_legacy_format(
    instance: Recorder, session: Session, purge_before: datetime
) -> bool:
    """Purge rows that are still linked by the event_ids."""
    (
        event_ids,
        state_ids,
        attributes_ids,
        data_ids,
    ) = _select_legacy_event_state_and_attributes_and_data_ids_to_purge(
        session, purge_before
    )
    _purge_state_ids(instance, session, state_ids)
    _purge_unused_attributes_ids(instance, session, attributes_ids)
    _purge_event_ids(session, event_ids)
    _purge_unused_data_ids(instance, session, data_ids)
    return bool(event_ids or state_ids or attributes_ids or data_ids)


def _purge_states_and_attributes_ids(
    instance: Recorder,
    session: Session,
    states_batch_size: int,
    purge_before: datetime,
) -> bool:
    """Purge states and linked attributes id in a batch.

    Returns true if there are more states to purge.
    """
    database_engine = instance.database_engine
    assert database_engine is not None
    has_remaining_state_ids_to_purge = True
    # There are more states relative to attributes_ids so
    # we purge enough state_ids to try to generate a full
    # size batch of attributes_ids that will be around the size
    # SQLITE_MAX_BIND_VARS
    attributes_ids_batch: set[int] = set()
    for _ in range(states_batch_size):
        state_ids, attributes_ids = _select_state_attributes_ids_to_purge(
            session, purge_before
        )
        if not state_ids:
            has_remaining_state_ids_to_purge = False
            break
        _purge_state_ids(instance, session, state_ids)
        attributes_ids_batch = attributes_ids_batch | attributes_ids

    _purge_unused_attributes_ids(instance, session, attributes_ids_batch)
    _LOGGER.debug(
        "After purging states and attributes_ids remaining=%s",
        has_remaining_state_ids_to_purge,
    )
    return has_remaining_state_ids_to_purge


def _purge_events_and_data_ids(
    instance: Recorder,
    session: Session,
    events_batch_size: int,
    purge_before: datetime,
) -> bool:
    """Purge states and linked attributes id in a batch.

    Returns true if there are more states to purge.
    """
    has_remaining_event_ids_to_purge = True
    # There are more events relative to data_ids so
    # we purge enough event_ids to try to generate a full
    # size batch of data_ids that will be around the size
    # SQLITE_MAX_BIND_VARS
    data_ids_batch: set[int] = set()
    for _ in range(events_batch_size):
        event_ids, data_ids = _select_event_data_ids_to_purge(session, purge_before)
        if not event_ids:
            has_remaining_event_ids_to_purge = False
            break
        _purge_event_ids(session, event_ids)
        data_ids_batch = data_ids_batch | data_ids

    _purge_unused_data_ids(instance, session, data_ids_batch)
    _LOGGER.debug(
        "After purging event and data_ids remaining=%s",
        has_remaining_event_ids_to_purge,
    )
    return has_remaining_event_ids_to_purge


def _select_state_attributes_ids_to_purge(
    session: Session, purge_before: datetime
) -> tuple[set[int], set[int]]:
    """Return sets of state and attribute ids to purge."""
    state_ids = set()
    attributes_ids = set()
    for state in session.execute(
        find_states_to_purge(dt_util.utc_to_timestamp(purge_before))
    ).all():
        state_ids.add(state.state_id)
        if state.attributes_id:
            attributes_ids.add(state.attributes_id)
    _LOGGER.debug(
        "Selected %s state ids and %s attributes_ids to remove",
        len(state_ids),
        len(attributes_ids),
    )
    return state_ids, attributes_ids


def _select_event_data_ids_to_purge(
    session: Session, purge_before: datetime
) -> tuple[set[int], set[int]]:
    """Return sets of event and data ids to purge."""
    event_ids = set()
    data_ids = set()
    for event in session.execute(
        find_events_to_purge(dt_util.utc_to_timestamp(purge_before))
    ).all():
        event_ids.add(event.event_id)
        if event.data_id:
            data_ids.add(event.data_id)
    _LOGGER.debug(
        "Selected %s event ids and %s data_ids to remove", len(event_ids), len(data_ids)
    )
    return event_ids, data_ids


def _select_unused_attributes_ids(
    session: Session, attributes_ids: set[int], database_engine: DatabaseEngine
) -> set[int]:
    """Return a set of attributes ids that are not used by any states in the db."""
    if not attributes_ids:
        return set()

    if not database_engine.optimizer.slow_range_in_select:
        #
        # SQLite has a superior query optimizer for the distinct query below as it uses
        # the covering index without having to examine the rows directly for both of the
        # queries below.
        #
        # We use the distinct query for SQLite since the query in the other branch can
        # generate more than 500 unions which SQLite does not support.
        #
        # How MariaDB's query optimizer handles this query:
        # > explain select distinct attributes_id from states where attributes_id in
        #   (136723);
        # ...Using index
        #
        seen_ids = {
            state[0]
            for state in session.execute(
                attributes_ids_exist_in_states_with_fast_in_distinct(attributes_ids)
            ).all()
        }
    else:
        #
        # This branch is for DBMS that cannot optimize the distinct query well and has
        # to examine all the rows that match.
        #
        # This branch uses a union of simple queries, as each query is optimized away
        # as the answer to the query can be found in the index.
        #
        # The below query works for SQLite as long as there are no more than 500
        # attributes_id to be selected. We currently do not have MySQL or PostgreSQL
        # servers running in the test suite; we test this path using SQLite when there
        # are less than 500 attributes_id.
        #
        # How MariaDB's query optimizer handles this query:
        # > explain select min(attributes_id) from states where attributes_id = 136723;
        # ...Select tables optimized away
        #
        # We used to generate a query based on how many attribute_ids to find but
        # that meant sqlalchemy Transparent SQL Compilation Caching was working against
        # us by cached up to SQLITE_MAX_BIND_VARS different statements which could be
        # up to 500MB for large database due to the complexity of the ORM objects.
        #
        # We now break the query into groups of 100 and use a lambda_stmt to ensure
        # that the query is only cached once.
        #
        seen_ids = set()
        groups = [iter(attributes_ids)] * 100
        for attr_ids in zip_longest(*groups, fillvalue=None):
            seen_ids |= {
                attrs_id[0]
                for attrs_id in session.execute(
                    attributes_ids_exist_in_states(*attr_ids)  # type: ignore[arg-type]
                ).all()
                if attrs_id[0] is not None
            }
    to_remove = attributes_ids - seen_ids
    _LOGGER.debug(
        "Selected %s shared attributes to remove",
        len(to_remove),
    )
    return to_remove


def _purge_unused_attributes_ids(
    instance: Recorder,
    session: Session,
    attributes_ids_batch: set[int],
) -> None:
    """Purge unused attributes ids."""
    database_engine = instance.database_engine
    assert database_engine is not None
    if unused_attribute_ids_set := _select_unused_attributes_ids(
        session, attributes_ids_batch, database_engine
    ):
        _purge_batch_attributes_ids(instance, session, unused_attribute_ids_set)


def _select_unused_event_data_ids(
    session: Session, data_ids: set[int], database_engine: DatabaseEngine
) -> set[int]:
    """Return a set of event data ids that are not used by any events in the db."""
    if not data_ids:
        return set()

    # See _select_unused_attributes_ids for why this function
    # branches for non-sqlite databases.
    if not database_engine.optimizer.slow_range_in_select:
        seen_ids = {
            state[0]
            for state in session.execute(
                data_ids_exist_in_events_with_fast_in_distinct(data_ids)
            ).all()
        }
    else:
        seen_ids = set()
        groups = [iter(data_ids)] * 100
        for data_ids_group in zip_longest(*groups, fillvalue=None):
            seen_ids |= {
                data_id[0]
                for data_id in session.execute(
                    data_ids_exist_in_events(*data_ids_group)  # type: ignore[arg-type]
                ).all()
                if data_id[0] is not None
            }
    to_remove = data_ids - seen_ids
    _LOGGER.debug("Selected %s shared event data to remove", len(to_remove))
    return to_remove


def _purge_unused_data_ids(
    instance: Recorder, session: Session, data_ids_batch: set[int]
) -> None:
    database_engine = instance.database_engine
    assert database_engine is not None
    if unused_data_ids_set := _select_unused_event_data_ids(
        session, data_ids_batch, database_engine
    ):
        _purge_batch_data_ids(instance, session, unused_data_ids_set)


def _select_statistics_runs_to_purge(
    session: Session, purge_before: datetime
) -> list[int]:
    """Return a list of statistic runs to purge.

    Takes care to keep the newest run.
    """
    statistic_runs = session.execute(find_statistics_runs_to_purge(purge_before)).all()
    statistic_runs_list = [run.run_id for run in statistic_runs]
    # Exclude the newest statistics run
    if (
        last_run := session.execute(find_latest_statistics_runs_run_id()).scalar()
    ) and last_run in statistic_runs_list:
        statistic_runs_list.remove(last_run)

    _LOGGER.debug("Selected %s statistic runs to remove", len(statistic_runs))
    return statistic_runs_list


def _select_short_term_statistics_to_purge(
    session: Session, purge_before: datetime
) -> list[int]:
    """Return a list of short term statistics to purge."""
    statistics = session.execute(
        find_short_term_statistics_to_purge(purge_before)
    ).all()
    _LOGGER.debug("Selected %s short term statistics to remove", len(statistics))
    return [statistic.id for statistic in statistics]


def _select_legacy_event_state_and_attributes_and_data_ids_to_purge(
    session: Session, purge_before: datetime
) -> tuple[set[int], set[int], set[int], set[int]]:
    """Return a list of event, state, and attribute ids to purge linked by the event_id.

    We do not link these anymore since state_change events
    do not exist in the events table anymore, however we
    still need to be able to purge them.
    """
    events = session.execute(
        find_legacy_event_state_and_attributes_and_data_ids_to_purge(
            dt_util.utc_to_timestamp(purge_before)
        )
    ).all()
    _LOGGER.debug("Selected %s event ids to remove", len(events))
    event_ids = set()
    state_ids = set()
    attributes_ids = set()
    data_ids = set()
    for event in events:
        event_ids.add(event.event_id)
        if event.state_id:
            state_ids.add(event.state_id)
        if event.attributes_id:
            attributes_ids.add(event.attributes_id)
        if event.data_id:
            data_ids.add(event.data_id)
    return event_ids, state_ids, attributes_ids, data_ids


def _purge_state_ids(instance: Recorder, session: Session, state_ids: set[int]) -> None:
    """Disconnect states and delete by state id."""
    if not state_ids:
        return

    # Update old_state_id to NULL before deleting to ensure
    # the delete does not fail due to a foreign key constraint
    # since some databases (MSSQL) cannot do the ON DELETE SET NULL
    # for us.
    disconnected_rows = session.execute(disconnect_states_rows(state_ids))
    _LOGGER.debug("Updated %s states to remove old_state_id", disconnected_rows)

    deleted_rows = session.execute(delete_states_rows(state_ids))
    _LOGGER.debug("Deleted %s states", deleted_rows)

    # Evict eny entries in the old_states cache referring to a purged state
    instance.states_manager.evict_purged_state_ids(state_ids)


def _purge_batch_attributes_ids(
    instance: Recorder, session: Session, attributes_ids: set[int]
) -> None:
    """Delete old attributes ids in batches of SQLITE_MAX_BIND_VARS."""
    for attributes_ids_chunk in chunked(attributes_ids, SQLITE_MAX_BIND_VARS):
        deleted_rows = session.execute(
            delete_states_attributes_rows(attributes_ids_chunk)
        )
        _LOGGER.debug("Deleted %s attribute states", deleted_rows)

    # Evict any entries in the state_attributes_ids cache referring to a purged state
    instance.state_attributes_manager.evict_purged(attributes_ids)


def _purge_batch_data_ids(
    instance: Recorder, session: Session, data_ids: set[int]
) -> None:
    """Delete old event data ids in batches of SQLITE_MAX_BIND_VARS."""
    for data_ids_chunk in chunked(data_ids, SQLITE_MAX_BIND_VARS):
        deleted_rows = session.execute(delete_event_data_rows(data_ids_chunk))
        _LOGGER.debug("Deleted %s data events", deleted_rows)

    # Evict any entries in the event_data_ids cache referring to a purged state
    instance.event_data_manager.evict_purged(data_ids)


def _purge_statistics_runs(session: Session, statistics_runs: list[int]) -> None:
    """Delete by run_id."""
    deleted_rows = session.execute(delete_statistics_runs_rows(statistics_runs))
    _LOGGER.debug("Deleted %s statistic runs", deleted_rows)


def _purge_short_term_statistics(
    session: Session, short_term_statistics: list[int]
) -> None:
    """Delete by id."""
    deleted_rows = session.execute(
        delete_statistics_short_term_rows(short_term_statistics)
    )
    _LOGGER.debug("Deleted %s short term statistics", deleted_rows)


def _purge_event_ids(session: Session, event_ids: set[int]) -> None:
    """Delete by event id."""
    if not event_ids:
        return
    deleted_rows = session.execute(delete_event_rows(event_ids))
    _LOGGER.debug("Deleted %s events", deleted_rows)


def _purge_old_recorder_runs(
    instance: Recorder, session: Session, purge_before: datetime
) -> None:
    """Purge all old recorder runs."""
    # Recorder runs is small, no need to batch run it
    deleted_rows = session.execute(
        delete_recorder_runs_rows(
            purge_before, instance.recorder_runs_manager.current.run_id
        )
    )
    _LOGGER.debug("Deleted %s recorder_runs", deleted_rows)


def _purge_old_event_types(instance: Recorder, session: Session) -> None:
    """Purge all old event types."""
    # Event types is small, no need to batch run it
    purge_event_types = set()
    event_type_ids = set()
    for event_type_id, event_type in session.execute(find_event_types_to_purge()):
        purge_event_types.add(event_type)
        event_type_ids.add(event_type_id)

    if not event_type_ids:
        return

    deleted_rows = session.execute(delete_event_types_rows(event_type_ids))
    _LOGGER.debug("Deleted %s event types", deleted_rows)

    # Evict any entries in the event_type cache referring to a purged state
    instance.event_type_manager.evict_purged(purge_event_types)


def _purge_old_entity_ids(instance: Recorder, session: Session) -> None:
    """Purge all old entity_ids."""
    # entity_ids are small, no need to batch run it
    purge_entity_ids = set()
    states_metadata_ids = set()
    for metadata_id, entity_id in session.execute(find_entity_ids_to_purge()):
        purge_entity_ids.add(entity_id)
        states_metadata_ids.add(metadata_id)

    if not states_metadata_ids:
        return

    deleted_rows = session.execute(delete_states_meta_rows(states_metadata_ids))
    _LOGGER.debug("Deleted %s states meta", deleted_rows)

    # Evict any entries in the event_type cache referring to a purged state
    instance.states_meta_manager.evict_purged(purge_entity_ids)
    instance.states_manager.evict_purged_entity_ids(purge_entity_ids)


def _purge_filtered_data(instance: Recorder, session: Session) -> bool:
    """Remove filtered states and events that shouldn't be in the database."""
    _LOGGER.debug("Cleanup filtered data")
    database_engine = instance.database_engine
    assert database_engine is not None
    now_timestamp = time.time()

    # Check if excluded entity_ids are in database
    entity_filter = instance.entity_filter
    has_more_states_to_purge = False
    excluded_metadata_ids: list[str] = [
        metadata_id
        for (metadata_id, entity_id) in session.query(
            StatesMeta.metadata_id, StatesMeta.entity_id
        ).all()
        if not entity_filter(entity_id)
    ]
    if excluded_metadata_ids:
        has_more_states_to_purge = _purge_filtered_states(
            instance, session, excluded_metadata_ids, database_engine, now_timestamp
        )

    # Check if excluded event_types are in database
    has_more_events_to_purge = False
    if (
        event_type_to_event_type_ids := instance.event_type_manager.get_many(
            instance.exclude_event_types, session
        )
    ) and (
        excluded_event_type_ids := [
            event_type_id
            for event_type_id in event_type_to_event_type_ids.values()
            if event_type_id is not None
        ]
    ):
        has_more_events_to_purge = _purge_filtered_events(
            instance, session, excluded_event_type_ids, now_timestamp
        )

    # Purge has completed if there are not more state or events to purge
    return not (has_more_states_to_purge or has_more_events_to_purge)


def _purge_filtered_states(
    instance: Recorder,
    session: Session,
    metadata_ids_to_purge: list[str],
    database_engine: DatabaseEngine,
    purge_before_timestamp: float,
) -> bool:
    """Remove filtered states and linked events.

    Return true if all states are purged
    """
    state_ids: tuple[int, ...]
    attributes_ids: tuple[int, ...]
    event_ids: tuple[int, ...]
    to_purge = list(
        session.query(States.state_id, States.attributes_id, States.event_id)
        .filter(States.metadata_id.in_(metadata_ids_to_purge))
        .filter(States.last_updated_ts < purge_before_timestamp)
        .limit(SQLITE_MAX_BIND_VARS)
        .all()
    )
    if not to_purge:
        return True
    state_ids, attributes_ids, event_ids = zip(*to_purge)
    filtered_event_ids = {id_ for id_ in event_ids if id_ is not None}
    _LOGGER.debug(
        "Selected %s state_ids to remove that should be filtered", len(state_ids)
    )
    _purge_state_ids(instance, session, set(state_ids))
    # These are legacy events that are linked to a state that are no longer
    # created but since we did not remove them when we stopped adding new ones
    # we will need to purge them here.
    _purge_event_ids(session, filtered_event_ids)
    unused_attribute_ids_set = _select_unused_attributes_ids(
        session, {id_ for id_ in attributes_ids if id_ is not None}, database_engine
    )
    _purge_batch_attributes_ids(instance, session, unused_attribute_ids_set)
    return False


def _purge_filtered_events(
    instance: Recorder,
    session: Session,
    excluded_event_type_ids: list[int],
    purge_before_timestamp: float,
) -> bool:
    """Remove filtered events and linked states.

    Return true if all events are purged.
    """
    database_engine = instance.database_engine
    assert database_engine is not None
    to_purge = list(
        session.query(Events.event_id, Events.data_id)
        .filter(Events.event_type_id.in_(excluded_event_type_ids))
        .filter(Events.time_fired_ts < purge_before_timestamp)
        .limit(SQLITE_MAX_BIND_VARS)
        .all()
    )
    if not to_purge:
        return True
    event_ids, data_ids = zip(*to_purge)
    event_ids_set = set(event_ids)
    _LOGGER.debug(
        "Selected %s event_ids to remove that should be filtered", len(event_ids_set)
    )
    if (
        instance.use_legacy_events_index
        and (
            states := session.query(States.state_id)
            .filter(States.event_id.in_(event_ids_set))
            .all()
        )
        and (state_ids := {state.state_id for state in states})
    ):
        # These are legacy states that are linked to an event that are no longer
        # created but since we did not remove them when we stopped adding new ones
        # we will need to purge them here.
        _purge_state_ids(instance, session, state_ids)
    _purge_event_ids(session, event_ids_set)
    if unused_data_ids_set := _select_unused_event_data_ids(
        session, set(data_ids), database_engine
    ):
        _purge_batch_data_ids(instance, session, unused_data_ids_set)
    return False


@retryable_database_job("purge_entity_data")
def purge_entity_data(
    instance: Recorder, entity_filter: Callable[[str], bool], purge_before: datetime
) -> bool:
    """Purge states and events of specified entities."""
    database_engine = instance.database_engine
    assert database_engine is not None
    purge_before_timestamp = purge_before.timestamp()
    with session_scope(session=instance.get_session()) as session:
        selected_metadata_ids: list[str] = [
            metadata_id
            for (metadata_id, entity_id) in session.query(
                StatesMeta.metadata_id, StatesMeta.entity_id
            ).all()
            if entity_filter(entity_id)
        ]
        _LOGGER.debug("Purging entity data for %s", selected_metadata_ids)
        if not selected_metadata_ids:
            return True

        # Purge a max of SQLITE_MAX_BIND_VARS, based on the oldest states
        # or events record.
        if not _purge_filtered_states(
            instance,
            session,
            selected_metadata_ids,
            database_engine,
            purge_before_timestamp,
        ):
            _LOGGER.debug("Purging entity data hasn't fully completed yet")
            return False

    return True
