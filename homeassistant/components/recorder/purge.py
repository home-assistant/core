"""Purge old data helper."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import distinct

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

    with session_scope(session=instance.get_session()) as session:  # type: ignore[misc]
        # Purge a max of MAX_ROWS_TO_PURGE, based on the oldest states or events record
        event_ids = _select_event_ids_to_purge(session, purge_before)
        state_ids, attributes_ids = _select_state_and_attributes_ids_to_purge(
            session, purge_before, event_ids
        )
        attribute_ids = _select_attribute_ids_to_purge(
            session, purge_before, attributes_ids
        )
        statistics_runs = _select_statistics_runs_to_purge(session, purge_before)
        short_term_statistics = _select_short_term_statistics_to_purge(
            session, purge_before
        )

        if state_ids:
            _purge_state_ids(instance, session, state_ids)

        if attribute_ids:
            _purge_attribute_ids(instance, session, attribute_ids)

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


def _select_event_ids_to_purge(session: Session, purge_before: datetime) -> list[int]:
    """Return a list of event ids to purge."""
    events = (
        session.query(Events.event_id)
        .filter(Events.time_fired < purge_before)
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    _LOGGER.debug("Selected %s event ids to remove", len(events))
    return [event.event_id for event in events]


def _select_state_and_attributes_ids_to_purge(
    session: Session, purge_before: datetime, event_ids: list[int]
) -> tuple[set[int], set[int]]:
    """Return a list of state ids to purge."""
    if not event_ids:
        return set(), set()
    states = (
        session.query(States.state_id, States.attributes_id)
        .filter(States.last_updated < purge_before)
        .filter(States.event_id.in_(event_ids))
        .all()
    )
    _LOGGER.debug("Selected %s state ids to remove", len(states))
    state_ids = set()
    attribute_ids = set()
    for state in states:
        state_ids.add(state.state_id)
        if state.attributes_ids:
            attribute_ids.add(state.attributes_ids)
    return state_ids, attribute_ids


def _select_attribute_ids_to_purge(
    session: Session, purge_before: datetime, attribute_ids: set[int]
) -> set[int]:
    """Return a list of attribute ids to purge."""
    if not attribute_ids:
        return set()
    keep_attribute_ids = {
        state.attributes_id
        for state in session.query(States.attributes_id)
        .filter(States.last_updated >= purge_before)
        .filter(States.attributes_id.in_(attribute_ids))
    }
    _LOGGER.debug(
        "Selected %s shared attributes to remove",
        len(attribute_ids - keep_attribute_ids),
    )
    return attribute_ids - keep_attribute_ids


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
    # Make a map from old_state_id to entity_id
    old_attributes = instance._state_attributes_ids  # pylint: disable=protected-access
    old_attributes_reversed = {
        attributes_id: attributes
        for attributes, attributes_id in old_attributes.items()
    }

    # Evict any purged state from the old states cache
    for purged_attribute_id in purged_attributes_ids.intersection(
        old_attributes_reversed
    ):
        old_attributes.pop(old_attributes_reversed[purged_attribute_id], None)


def _purge_attribute_ids(
    instance: Recorder, session: Session, attributes_ids: set[int]
) -> None:
    """Delete old attributes ids."""

    deleted_rows = (
        session.query(StateAttributes)
        .filter(StateAttributes.attributes_id.in_(attributes_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s attribute states", deleted_rows)

    # Evict eny entries in the old_states cache referring to a purged state
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


def _purge_event_ids(session: Session, event_ids: list[int]) -> None:
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
        .filter(RecorderRuns.run_id != instance.run_info.run_id)
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s recorder_runs", deleted_rows)


def _purge_filtered_data(instance: Recorder, session: Session) -> bool:
    """Remove filtered states and events that shouldn't be in the database."""
    _LOGGER.debug("Cleanup filtered data")

    # Check if excluded entity_ids are in database
    excluded_entity_ids: list[str] = [
        entity_id
        for (entity_id,) in session.query(distinct(States.entity_id)).all()
        if not instance.entity_filter(entity_id)
    ]
    if len(excluded_entity_ids) > 0:
        _purge_filtered_states(instance, session, excluded_entity_ids)
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
    instance: Recorder, session: Session, excluded_entity_ids: list[str]
) -> None:
    """Remove filtered states and linked events."""
    state_ids: list[int]
    event_ids: list[int | None]
    state_ids, event_ids = zip(
        *(
            session.query(States.state_id, States.event_id)
            .filter(States.entity_id.in_(excluded_entity_ids))
            .limit(MAX_ROWS_TO_PURGE)
            .all()
        )
    )
    # TODO: find attributes ids to purge as well
    event_ids = [id_ for id_ in event_ids if id_ is not None]
    _LOGGER.debug(
        "Selected %s state_ids to remove that should be filtered", len(state_ids)
    )
    _purge_state_ids(instance, session, set(state_ids))
    _purge_event_ids(session, event_ids)  # type: ignore[arg-type]  # type of event_ids already narrowed to 'list[int]'


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
    event_ids: list[int] = [event.event_id for event in events]
    _LOGGER.debug(
        "Selected %s event_ids to remove that should be filtered", len(event_ids)
    )
    states: list[States] = (
        session.query(States.state_id).filter(States.event_id.in_(event_ids)).all()
    )
    # TODO: find attributes ids to purge as well
    state_ids: set[int] = {state.state_id for state in states}
    _purge_state_ids(instance, session, state_ids)
    _purge_event_ids(session, event_ids)


@retryable_database_job("purge")
def purge_entity_data(instance: Recorder, entity_filter: Callable[[str], bool]) -> bool:
    """Purge states and events of specified entities."""
    with session_scope(session=instance.get_session()) as session:  # type: ignore[misc]
        selected_entity_ids: list[str] = [
            entity_id
            for (entity_id,) in session.query(distinct(States.entity_id)).all()
            if entity_filter(entity_id)
        ]
        _LOGGER.debug("Purging entity data for %s", selected_entity_ids)
        if len(selected_entity_ids) > 0:
            # Purge a max of MAX_ROWS_TO_PURGE, based on the oldest states or events record
            _purge_filtered_states(instance, session, selected_entity_ids)
            _LOGGER.debug("Purging entity data hasn't fully completed yet")
            return False

    return True
