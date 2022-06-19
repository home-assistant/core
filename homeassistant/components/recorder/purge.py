"""Purge old data helper."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from functools import partial
from itertools import islice, zip_longest
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import distinct

from homeassistant.const import EVENT_STATE_CHANGED

from .const import MAX_ROWS_TO_PURGE, SupportedDialect
from .db_schema import Events, StateAttributes, States
from .queries import (
    attributes_ids_exist_in_states,
    attributes_ids_exist_in_states_sqlite,
    data_ids_exist_in_events,
    data_ids_exist_in_events_sqlite,
    delete_event_data_rows,
    delete_event_rows,
    delete_recorder_runs_rows,
    delete_states_attributes_rows,
    delete_states_rows,
    delete_statistics_runs_rows,
    delete_statistics_short_term_rows,
    disconnect_states_rows,
    find_events_to_purge,
    find_latest_statistics_runs_run_id,
    find_legacy_event_state_and_attributes_and_data_ids_to_purge,
    find_legacy_row,
    find_short_term_statistics_to_purge,
    find_states_to_purge,
    find_statistics_runs_to_purge,
)
from .repack import repack_database
from .util import retryable_database_job, session_scope

if TYPE_CHECKING:
    from . import Recorder

_LOGGER = logging.getLogger(__name__)


DEFAULT_STATES_BATCHES_PER_PURGE = 20  # We expect ~95% de-dupe rate
DEFAULT_EVENTS_BATCHES_PER_PURGE = 15  # We expect ~92% de-dupe rate


def take(take_num: int, iterable: Iterable) -> list[Any]:
    """Return first n items of the iterable as a list.

    From itertools recipes
    """
    return list(islice(iterable, take_num))


def chunked(iterable: Iterable, chunked_num: int) -> Iterable[Any]:
    """Break *iterable* into lists of length *n*.

    From more-itertools
    """
    return iter(partial(take, chunked_num, iter(iterable)), [])


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
    using_sqlite = instance.dialect_name == SupportedDialect.SQLITE

    with session_scope(session=instance.get_session()) as session:
        # Purge a max of MAX_ROWS_TO_PURGE, based on the oldest states or events record
        has_more_to_purge = False
        if _purging_legacy_format(session):
            _LOGGER.debug(
                "Purge running in legacy format as there are states with event_id remaining"
            )
            has_more_to_purge |= _purge_legacy_format(
                instance, session, purge_before, using_sqlite
            )
        else:
            _LOGGER.debug(
                "Purge running in new format as there are NO states with event_id remaining"
            )
            # Once we are done purging legacy rows, we use the new method
            has_more_to_purge |= _purge_states_and_attributes_ids(
                instance, session, states_batch_size, purge_before, using_sqlite
            )
            has_more_to_purge |= _purge_events_and_data_ids(
                instance, session, events_batch_size, purge_before, using_sqlite
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

        _purge_old_recorder_runs(instance, session, purge_before)
    if repack:
        repack_database(instance)
    return True


def _purging_legacy_format(session: Session) -> bool:
    """Check if there are any legacy event_id linked states rows remaining."""
    return bool(session.execute(find_legacy_row()).scalar())


def _purge_legacy_format(
    instance: Recorder, session: Session, purge_before: datetime, using_sqlite: bool
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
    if state_ids:
        _purge_state_ids(instance, session, state_ids)
    _purge_unused_attributes_ids(instance, session, attributes_ids, using_sqlite)
    if event_ids:
        _purge_event_ids(session, event_ids)
    _purge_unused_data_ids(instance, session, data_ids, using_sqlite)
    return bool(event_ids or state_ids or attributes_ids or data_ids)


def _purge_states_and_attributes_ids(
    instance: Recorder,
    session: Session,
    states_batch_size: int,
    purge_before: datetime,
    using_sqlite: bool,
) -> bool:
    """Purge states and linked attributes id in a batch.

    Returns true if there are more states to purge.
    """
    has_remaining_state_ids_to_purge = True
    # There are more states relative to attributes_ids so
    # we purge enough state_ids to try to generate a full
    # size batch of attributes_ids that will be around the size
    # MAX_ROWS_TO_PURGE
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

    _purge_unused_attributes_ids(instance, session, attributes_ids_batch, using_sqlite)
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
    using_sqlite: bool,
) -> bool:
    """Purge states and linked attributes id in a batch.

    Returns true if there are more states to purge.
    """
    has_remaining_event_ids_to_purge = True
    # There are more events relative to data_ids so
    # we purge enough event_ids to try to generate a full
    # size batch of data_ids that will be around the size
    # MAX_ROWS_TO_PURGE
    data_ids_batch: set[int] = set()
    for _ in range(events_batch_size):
        event_ids, data_ids = _select_event_data_ids_to_purge(session, purge_before)
        if not event_ids:
            has_remaining_event_ids_to_purge = False
            break
        _purge_event_ids(session, event_ids)
        data_ids_batch = data_ids_batch | data_ids

    _purge_unused_data_ids(instance, session, data_ids_batch, using_sqlite)
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
    for state in session.execute(find_states_to_purge(purge_before)).all():
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
    for event in session.execute(find_events_to_purge(purge_before)).all():
        event_ids.add(event.event_id)
        if event.data_id:
            data_ids.add(event.data_id)
    _LOGGER.debug(
        "Selected %s event ids and %s data_ids to remove", len(event_ids), len(data_ids)
    )
    return event_ids, data_ids


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
            for state in session.execute(
                attributes_ids_exist_in_states_sqlite(attributes_ids)
            ).all()
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
        # us by cached up to MAX_ROWS_TO_PURGE different statements which could be
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
    using_sqlite: bool,
) -> None:
    if unused_attribute_ids_set := _select_unused_attributes_ids(
        session, attributes_ids_batch, using_sqlite
    ):
        _purge_batch_attributes_ids(instance, session, unused_attribute_ids_set)


def _select_unused_event_data_ids(
    session: Session, data_ids: set[int], using_sqlite: bool
) -> set[int]:
    """Return a set of event data ids that are not used by any events in the database."""
    if not data_ids:
        return set()

    # See _select_unused_attributes_ids for why this function
    # branches for non-sqlite databases.
    if using_sqlite:
        seen_ids = {
            state[0]
            for state in session.execute(
                data_ids_exist_in_events_sqlite(data_ids)
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
    instance: Recorder, session: Session, data_ids_batch: set[int], using_sqlite: bool
) -> None:

    if unused_data_ids_set := _select_unused_event_data_ids(
        session, data_ids_batch, using_sqlite
    ):
        _purge_batch_data_ids(instance, session, unused_data_ids_set)


def _select_statistics_runs_to_purge(
    session: Session, purge_before: datetime
) -> list[int]:
    """Return a list of statistic runs to purge, but take care to keep the newest run."""
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
    """Return a list of event, state, and attribute ids to purge that are linked by the event_id.

    We do not link these anymore since state_change events
    do not exist in the events table anymore, however we
    still need to be able to purge them.
    """
    events = session.execute(
        find_legacy_event_state_and_attributes_and_data_ids_to_purge(purge_before)
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

    # Update old_state_id to NULL before deleting to ensure
    # the delete does not fail due to a foreign key constraint
    # since some databases (MSSQL) cannot do the ON DELETE SET NULL
    # for us.
    disconnected_rows = session.execute(disconnect_states_rows(state_ids))
    _LOGGER.debug("Updated %s states to remove old_state_id", disconnected_rows)

    deleted_rows = session.execute(delete_states_rows(state_ids))
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


def _evict_purged_data_from_data_cache(
    instance: Recorder, purged_data_ids: set[int]
) -> None:
    """Evict purged data ids from the data ids cache."""
    # Make a map from data_id to the data json
    event_data_ids = instance._event_data_ids  # pylint: disable=protected-access
    event_data_ids_reversed = {
        data_id: data for data, data_id in event_data_ids.items()
    }

    # Evict any purged data from the event_data_ids cache
    for purged_attribute_id in purged_data_ids.intersection(event_data_ids_reversed):
        event_data_ids.pop(event_data_ids_reversed[purged_attribute_id], None)


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


def _purge_batch_attributes_ids(
    instance: Recorder, session: Session, attributes_ids: set[int]
) -> None:
    """Delete old attributes ids in batches of MAX_ROWS_TO_PURGE."""
    for attributes_ids_chunk in chunked(attributes_ids, MAX_ROWS_TO_PURGE):
        deleted_rows = session.execute(
            delete_states_attributes_rows(attributes_ids_chunk)
        )
        _LOGGER.debug("Deleted %s attribute states", deleted_rows)

    # Evict any entries in the state_attributes_ids cache referring to a purged state
    _evict_purged_attributes_from_attributes_cache(instance, attributes_ids)


def _purge_batch_data_ids(
    instance: Recorder, session: Session, data_ids: set[int]
) -> None:
    """Delete old event data ids in batches of MAX_ROWS_TO_PURGE."""
    for data_ids_chunk in chunked(data_ids, MAX_ROWS_TO_PURGE):
        deleted_rows = session.execute(delete_event_data_rows(data_ids_chunk))
        _LOGGER.debug("Deleted %s data events", deleted_rows)

    # Evict any entries in the event_data_ids cache referring to a purged state
    _evict_purged_data_from_data_cache(instance, data_ids)


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


def _purge_event_ids(session: Session, event_ids: Iterable[int]) -> None:
    """Delete by event id."""
    deleted_rows = session.execute(delete_event_rows(event_ids))
    _LOGGER.debug("Deleted %s events", deleted_rows)


def _purge_old_recorder_runs(
    instance: Recorder, session: Session, purge_before: datetime
) -> None:
    """Purge all old recorder runs."""
    # Recorder runs is small, no need to batch run it
    deleted_rows = session.execute(
        delete_recorder_runs_rows(purge_before, instance.run_history.current.run_id)
    )
    _LOGGER.debug("Deleted %s recorder_runs", deleted_rows)


def _purge_filtered_data(instance: Recorder, session: Session) -> bool:
    """Remove filtered states and events that shouldn't be in the database."""
    _LOGGER.debug("Cleanup filtered data")
    using_sqlite = instance.dialect_name == SupportedDialect.SQLITE

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
    _purge_batch_attributes_ids(instance, session, unused_attribute_ids_set)


def _purge_filtered_events(
    instance: Recorder, session: Session, excluded_event_types: list[str]
) -> None:
    """Remove filtered events and linked states."""
    using_sqlite = instance.dialect_name == SupportedDialect.SQLITE
    event_ids, data_ids = zip(
        *(
            session.query(Events.event_id, Events.data_id)
            .filter(Events.event_type.in_(excluded_event_types))
            .limit(MAX_ROWS_TO_PURGE)
            .all()
        )
    )
    _LOGGER.debug(
        "Selected %s event_ids to remove that should be filtered", len(event_ids)
    )
    states: list[States] = (
        session.query(States.state_id).filter(States.event_id.in_(event_ids)).all()
    )
    state_ids: set[int] = {state.state_id for state in states}
    _purge_state_ids(instance, session, state_ids)
    _purge_event_ids(session, event_ids)
    if unused_data_ids_set := _select_unused_event_data_ids(
        session, set(data_ids), using_sqlite
    ):
        _purge_batch_data_ids(instance, session, unused_data_ids_set)
    if EVENT_STATE_CHANGED in excluded_event_types:
        session.query(StateAttributes).delete(synchronize_session=False)
        instance._state_attributes_ids = {}  # pylint: disable=protected-access


@retryable_database_job("purge")
def purge_entity_data(instance: Recorder, entity_filter: Callable[[str], bool]) -> bool:
    """Purge states and events of specified entities."""
    using_sqlite = instance.dialect_name == SupportedDialect.SQLITE
    with session_scope(session=instance.get_session()) as session:
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
