"""Purge old data helper."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from itertools import zip_longest
import logging
from typing import TYPE_CHECKING

from sqlalchemy import func, lambda_stmt, select, union_all
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import distinct
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Select

from homeassistant.const import EVENT_STATE_CHANGED

from .const import MAX_ROWS_TO_PURGE
from .models import (
    EventData,
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
            data_ids,
        ) = _select_event_state_attributes_ids_data_ids_to_purge(session, purge_before)
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

        if unused_data_ids_set := _select_unused_event_data_ids(
            session, data_ids, using_sqlite
        ):
            _purge_event_data_ids(instance, session, unused_data_ids_set)

        if statistics_runs:
            _purge_statistics_runs(session, statistics_runs)

        if short_term_statistics:
            _purge_short_term_statistics(session, short_term_statistics)

        if state_ids or event_ids or statistics_runs or short_term_statistics:
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


def _select_event_state_attributes_ids_data_ids_to_purge(
    session: Session, purge_before: datetime
) -> tuple[set[int], set[int], set[int], set[int]]:
    """Return a list of event, state, and attribute ids to purge."""
    events = (
        session.query(Events.event_id, Events.data_id)
        .filter(Events.time_fired < purge_before)
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    _LOGGER.debug("Selected %s event ids to remove", len(events))
    states = (
        session.query(States.state_id, States.attributes_id)
        .filter(States.last_updated < purge_before)
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    _LOGGER.debug("Selected %s state ids to remove", len(states))
    event_ids = set()
    state_ids = set()
    attributes_ids = set()
    data_ids = set()
    for event in events:
        event_ids.add(event.event_id)
        if event.data_id:
            data_ids.add(event.data_id)
    for state in states:
        state_ids.add(state.state_id)
        if state.attributes_id:
            attributes_ids.add(state.attributes_id)
    return event_ids, state_ids, attributes_ids, data_ids


def _state_attrs_exist(attr: int | None) -> Select:
    """Check if a state attributes id exists in the states table."""
    return select(func.min(States.attributes_id)).where(States.attributes_id == attr)


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
    """Generate the find attributes select only once.

    https://docs.sqlalchemy.org/en/14/core/connections.html#quick-guidelines-for-lambdas
    """
    return lambda_stmt(
        lambda: union_all(
            _state_attrs_exist(attr1),
            _state_attrs_exist(attr2),
            _state_attrs_exist(attr3),
            _state_attrs_exist(attr4),
            _state_attrs_exist(attr5),
            _state_attrs_exist(attr6),
            _state_attrs_exist(attr7),
            _state_attrs_exist(attr8),
            _state_attrs_exist(attr9),
            _state_attrs_exist(attr10),
            _state_attrs_exist(attr11),
            _state_attrs_exist(attr12),
            _state_attrs_exist(attr13),
            _state_attrs_exist(attr14),
            _state_attrs_exist(attr15),
            _state_attrs_exist(attr16),
            _state_attrs_exist(attr17),
            _state_attrs_exist(attr18),
            _state_attrs_exist(attr19),
            _state_attrs_exist(attr20),
            _state_attrs_exist(attr21),
            _state_attrs_exist(attr22),
            _state_attrs_exist(attr23),
            _state_attrs_exist(attr24),
            _state_attrs_exist(attr25),
            _state_attrs_exist(attr26),
            _state_attrs_exist(attr27),
            _state_attrs_exist(attr28),
            _state_attrs_exist(attr29),
            _state_attrs_exist(attr30),
            _state_attrs_exist(attr31),
            _state_attrs_exist(attr32),
            _state_attrs_exist(attr33),
            _state_attrs_exist(attr34),
            _state_attrs_exist(attr35),
            _state_attrs_exist(attr36),
            _state_attrs_exist(attr37),
            _state_attrs_exist(attr38),
            _state_attrs_exist(attr39),
            _state_attrs_exist(attr40),
            _state_attrs_exist(attr41),
            _state_attrs_exist(attr42),
            _state_attrs_exist(attr43),
            _state_attrs_exist(attr44),
            _state_attrs_exist(attr45),
            _state_attrs_exist(attr46),
            _state_attrs_exist(attr47),
            _state_attrs_exist(attr48),
            _state_attrs_exist(attr49),
            _state_attrs_exist(attr50),
            _state_attrs_exist(attr51),
            _state_attrs_exist(attr52),
            _state_attrs_exist(attr53),
            _state_attrs_exist(attr54),
            _state_attrs_exist(attr55),
            _state_attrs_exist(attr56),
            _state_attrs_exist(attr57),
            _state_attrs_exist(attr58),
            _state_attrs_exist(attr59),
            _state_attrs_exist(attr60),
            _state_attrs_exist(attr61),
            _state_attrs_exist(attr62),
            _state_attrs_exist(attr63),
            _state_attrs_exist(attr64),
            _state_attrs_exist(attr65),
            _state_attrs_exist(attr66),
            _state_attrs_exist(attr67),
            _state_attrs_exist(attr68),
            _state_attrs_exist(attr69),
            _state_attrs_exist(attr70),
            _state_attrs_exist(attr71),
            _state_attrs_exist(attr72),
            _state_attrs_exist(attr73),
            _state_attrs_exist(attr74),
            _state_attrs_exist(attr75),
            _state_attrs_exist(attr76),
            _state_attrs_exist(attr77),
            _state_attrs_exist(attr78),
            _state_attrs_exist(attr79),
            _state_attrs_exist(attr80),
            _state_attrs_exist(attr81),
            _state_attrs_exist(attr82),
            _state_attrs_exist(attr83),
            _state_attrs_exist(attr84),
            _state_attrs_exist(attr85),
            _state_attrs_exist(attr86),
            _state_attrs_exist(attr87),
            _state_attrs_exist(attr88),
            _state_attrs_exist(attr89),
            _state_attrs_exist(attr90),
            _state_attrs_exist(attr91),
            _state_attrs_exist(attr92),
            _state_attrs_exist(attr93),
            _state_attrs_exist(attr94),
            _state_attrs_exist(attr95),
            _state_attrs_exist(attr96),
            _state_attrs_exist(attr97),
            _state_attrs_exist(attr98),
            _state_attrs_exist(attr99),
            _state_attrs_exist(attr100),
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


def _event_data_id_exist(data_id: int | None) -> Select:
    """Check if a event data id exists in the events table."""
    return select(func.min(Events.data_id)).where(Events.data_id == data_id)


def _generate_find_data_id_lambda(
    id1: int,
    id2: int | None,
    id3: int | None,
    id4: int | None,
    id5: int | None,
    id6: int | None,
    id7: int | None,
    id8: int | None,
    id9: int | None,
    id10: int | None,
    id11: int | None,
    id12: int | None,
    id13: int | None,
    id14: int | None,
    id15: int | None,
    id16: int | None,
    id17: int | None,
    id18: int | None,
    id19: int | None,
    id20: int | None,
    id21: int | None,
    id22: int | None,
    id23: int | None,
    id24: int | None,
    id25: int | None,
    id26: int | None,
    id27: int | None,
    id28: int | None,
    id29: int | None,
    id30: int | None,
    id31: int | None,
    id32: int | None,
    id33: int | None,
    id34: int | None,
    id35: int | None,
    id36: int | None,
    id37: int | None,
    id38: int | None,
    id39: int | None,
    id40: int | None,
    id41: int | None,
    id42: int | None,
    id43: int | None,
    id44: int | None,
    id45: int | None,
    id46: int | None,
    id47: int | None,
    id48: int | None,
    id49: int | None,
    id50: int | None,
    id51: int | None,
    id52: int | None,
    id53: int | None,
    id54: int | None,
    id55: int | None,
    id56: int | None,
    id57: int | None,
    id58: int | None,
    id59: int | None,
    id60: int | None,
    id61: int | None,
    id62: int | None,
    id63: int | None,
    id64: int | None,
    id65: int | None,
    id66: int | None,
    id67: int | None,
    id68: int | None,
    id69: int | None,
    id70: int | None,
    id71: int | None,
    id72: int | None,
    id73: int | None,
    id74: int | None,
    id75: int | None,
    id76: int | None,
    id77: int | None,
    id78: int | None,
    id79: int | None,
    id80: int | None,
    id81: int | None,
    id82: int | None,
    id83: int | None,
    id84: int | None,
    id85: int | None,
    id86: int | None,
    id87: int | None,
    id88: int | None,
    id89: int | None,
    id90: int | None,
    id91: int | None,
    id92: int | None,
    id93: int | None,
    id94: int | None,
    id95: int | None,
    id96: int | None,
    id97: int | None,
    id98: int | None,
    id99: int | None,
    id100: int | None,
) -> StatementLambdaElement:
    """Generate the find event data select only once.

    https://docs.sqlalchemy.org/en/14/core/connections.html#quick-guidelines-for-lambdas
    """
    return lambda_stmt(
        lambda: union_all(
            _event_data_id_exist(id1),
            _event_data_id_exist(id2),
            _event_data_id_exist(id3),
            _event_data_id_exist(id4),
            _event_data_id_exist(id5),
            _event_data_id_exist(id6),
            _event_data_id_exist(id7),
            _event_data_id_exist(id8),
            _event_data_id_exist(id9),
            _event_data_id_exist(id10),
            _event_data_id_exist(id11),
            _event_data_id_exist(id12),
            _event_data_id_exist(id13),
            _event_data_id_exist(id14),
            _event_data_id_exist(id15),
            _event_data_id_exist(id16),
            _event_data_id_exist(id17),
            _event_data_id_exist(id18),
            _event_data_id_exist(id19),
            _event_data_id_exist(id20),
            _event_data_id_exist(id21),
            _event_data_id_exist(id22),
            _event_data_id_exist(id23),
            _event_data_id_exist(id24),
            _event_data_id_exist(id25),
            _event_data_id_exist(id26),
            _event_data_id_exist(id27),
            _event_data_id_exist(id28),
            _event_data_id_exist(id29),
            _event_data_id_exist(id30),
            _event_data_id_exist(id31),
            _event_data_id_exist(id32),
            _event_data_id_exist(id33),
            _event_data_id_exist(id34),
            _event_data_id_exist(id35),
            _event_data_id_exist(id36),
            _event_data_id_exist(id37),
            _event_data_id_exist(id38),
            _event_data_id_exist(id39),
            _event_data_id_exist(id40),
            _event_data_id_exist(id41),
            _event_data_id_exist(id42),
            _event_data_id_exist(id43),
            _event_data_id_exist(id44),
            _event_data_id_exist(id45),
            _event_data_id_exist(id46),
            _event_data_id_exist(id47),
            _event_data_id_exist(id48),
            _event_data_id_exist(id49),
            _event_data_id_exist(id50),
            _event_data_id_exist(id51),
            _event_data_id_exist(id52),
            _event_data_id_exist(id53),
            _event_data_id_exist(id54),
            _event_data_id_exist(id55),
            _event_data_id_exist(id56),
            _event_data_id_exist(id57),
            _event_data_id_exist(id58),
            _event_data_id_exist(id59),
            _event_data_id_exist(id60),
            _event_data_id_exist(id61),
            _event_data_id_exist(id62),
            _event_data_id_exist(id63),
            _event_data_id_exist(id64),
            _event_data_id_exist(id65),
            _event_data_id_exist(id66),
            _event_data_id_exist(id67),
            _event_data_id_exist(id68),
            _event_data_id_exist(id69),
            _event_data_id_exist(id70),
            _event_data_id_exist(id71),
            _event_data_id_exist(id72),
            _event_data_id_exist(id73),
            _event_data_id_exist(id74),
            _event_data_id_exist(id75),
            _event_data_id_exist(id76),
            _event_data_id_exist(id77),
            _event_data_id_exist(id78),
            _event_data_id_exist(id79),
            _event_data_id_exist(id80),
            _event_data_id_exist(id81),
            _event_data_id_exist(id82),
            _event_data_id_exist(id83),
            _event_data_id_exist(id84),
            _event_data_id_exist(id85),
            _event_data_id_exist(id86),
            _event_data_id_exist(id87),
            _event_data_id_exist(id88),
            _event_data_id_exist(id89),
            _event_data_id_exist(id90),
            _event_data_id_exist(id91),
            _event_data_id_exist(id92),
            _event_data_id_exist(id93),
            _event_data_id_exist(id94),
            _event_data_id_exist(id95),
            _event_data_id_exist(id96),
            _event_data_id_exist(id97),
            _event_data_id_exist(id98),
            _event_data_id_exist(id99),
            _event_data_id_exist(id100),
        )
    )


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
            for state in session.query(distinct(Events.data_id))
            .filter(Events.data_id.in_(data_ids))
            .all()
        }
    else:
        seen_ids = set()
        groups = [iter(data_ids)] * 100
        for data_ids_group in zip_longest(*groups, fillvalue=None):
            seen_ids |= {
                state[0]
                for state in session.execute(
                    _generate_find_data_id_lambda(*data_ids_group)
                ).all()
                if state[0] is not None
            }
    to_remove = data_ids - seen_ids
    _LOGGER.debug("Selected %s shared event data to remove", len(to_remove))
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


def _purge_event_data_ids(
    instance: Recorder, session: Session, data_ids: set[int]
) -> None:
    """Delete old event data ids."""

    deleted_rows = (
        session.query(EventData)
        .filter(EventData.data_id.in_(data_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s data events", deleted_rows)

    # Evict any entries in the event_data_ids cache referring to a purged state
    _evict_purged_data_from_data_cache(instance, data_ids)


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
    using_sqlite = instance.using_sqlite()
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
        _purge_event_data_ids(instance, session, unused_data_ids_set)
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
