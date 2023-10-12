"""Queries for the recorder."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import cast

from sqlalchemy import delete, distinct, func, lambda_stmt, select, union_all, update
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.roles import CompoundElementRole
from sqlalchemy.sql.selectable import Select

from .const import SQLITE_MAX_BIND_VARS
from .db_schema import (
    EventData,
    Events,
    EventTypes,
    RecorderRuns,
    StateAttributes,
    States,
    StatesMeta,
    StatisticsRuns,
    StatisticsShortTerm,
)


def select_event_type_ids(event_types: tuple[str, ...]) -> Select:
    """Generate a select for event type ids.

    This query is intentionally not a lambda statement as it is used inside
    other lambda statements.
    """
    return select(EventTypes.event_type_id).where(
        EventTypes.event_type.in_(event_types)
    )


def get_shared_attributes(hashes: list[int]) -> StatementLambdaElement:
    """Load shared attributes from the database."""
    return lambda_stmt(
        lambda: select(
            StateAttributes.attributes_id, StateAttributes.shared_attrs
        ).where(StateAttributes.hash.in_(hashes))
    )


def get_shared_event_datas(hashes: list[int]) -> StatementLambdaElement:
    """Load shared event data from the database."""
    return lambda_stmt(
        lambda: select(EventData.data_id, EventData.shared_data).where(
            EventData.hash.in_(hashes)
        )
    )


def find_event_type_ids(event_types: Iterable[str]) -> StatementLambdaElement:
    """Find an event_type id by event_type."""
    return lambda_stmt(
        lambda: select(EventTypes.event_type_id, EventTypes.event_type).filter(
            EventTypes.event_type.in_(event_types)
        )
    )


def find_all_states_metadata_ids() -> StatementLambdaElement:
    """Find all metadata_ids and entity_ids."""
    return lambda_stmt(lambda: select(StatesMeta.metadata_id, StatesMeta.entity_id))


def find_states_metadata_ids(entity_ids: Iterable[str]) -> StatementLambdaElement:
    """Find metadata_ids by entity_ids."""
    return lambda_stmt(
        lambda: select(StatesMeta.metadata_id, StatesMeta.entity_id).filter(
            StatesMeta.entity_id.in_(entity_ids)
        )
    )


def _state_attrs_exist(attr: int | None) -> Select:
    """Check if a state attributes id exists in the states table."""
    return select(func.min(States.attributes_id)).where(States.attributes_id == attr)


def attributes_ids_exist_in_states_with_fast_in_distinct(
    attributes_ids: Iterable[int],
) -> StatementLambdaElement:
    """Find attributes ids that exist in the states table."""
    return lambda_stmt(
        lambda: select(distinct(States.attributes_id)).filter(
            States.attributes_id.in_(attributes_ids)
        )
    )


def attributes_ids_exist_in_states(
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


def data_ids_exist_in_events_with_fast_in_distinct(
    data_ids: Iterable[int],
) -> StatementLambdaElement:
    """Find data ids that exist in the events table."""
    return lambda_stmt(
        lambda: select(distinct(Events.data_id)).filter(Events.data_id.in_(data_ids))
    )


def _event_data_id_exist(data_id: int | None) -> Select:
    """Check if a event data id exists in the events table."""
    return select(func.min(Events.data_id)).where(Events.data_id == data_id)


def data_ids_exist_in_events(
    data_ids: list[int | None],
) -> StatementLambdaElement:
    """Generate the find event data select only once.

    https://docs.sqlalchemy.org/en/14/core/connections.html#quick-guidelines-for-lambdas
    """
    _data_ids_exist = []
    for _id in data_ids:
        _data_ids_exist.append(_event_data_id_exist(_id))
    return lambda_stmt(lambda: union_all(cast(CompoundElementRole, _data_ids_exist)))


def disconnect_states_rows(state_ids: Iterable[int]) -> StatementLambdaElement:
    """Disconnect states rows."""
    return lambda_stmt(
        lambda: update(States)
        .where(States.old_state_id.in_(state_ids))
        .values(old_state_id=None)
        .execution_options(synchronize_session=False)
    )


def delete_states_rows(state_ids: Iterable[int]) -> StatementLambdaElement:
    """Delete states rows."""
    return lambda_stmt(
        lambda: delete(States)
        .where(States.state_id.in_(state_ids))
        .execution_options(synchronize_session=False)
    )


def delete_event_data_rows(data_ids: Iterable[int]) -> StatementLambdaElement:
    """Delete event_data rows."""
    return lambda_stmt(
        lambda: delete(EventData)
        .where(EventData.data_id.in_(data_ids))
        .execution_options(synchronize_session=False)
    )


def delete_states_attributes_rows(
    attributes_ids: Iterable[int],
) -> StatementLambdaElement:
    """Delete states_attributes rows."""
    return lambda_stmt(
        lambda: delete(StateAttributes)
        .where(StateAttributes.attributes_id.in_(attributes_ids))
        .execution_options(synchronize_session=False)
    )


def delete_statistics_runs_rows(
    statistics_runs: Iterable[int],
) -> StatementLambdaElement:
    """Delete statistics_runs rows."""
    return lambda_stmt(
        lambda: delete(StatisticsRuns)
        .where(StatisticsRuns.run_id.in_(statistics_runs))
        .execution_options(synchronize_session=False)
    )


def delete_statistics_short_term_rows(
    short_term_statistics: Iterable[int],
) -> StatementLambdaElement:
    """Delete statistics_short_term rows."""
    return lambda_stmt(
        lambda: delete(StatisticsShortTerm)
        .where(StatisticsShortTerm.id.in_(short_term_statistics))
        .execution_options(synchronize_session=False)
    )


def delete_event_rows(
    event_ids: Iterable[int],
) -> StatementLambdaElement:
    """Delete statistics_short_term rows."""
    return lambda_stmt(
        lambda: delete(Events)
        .where(Events.event_id.in_(event_ids))
        .execution_options(synchronize_session=False)
    )


def delete_recorder_runs_rows(
    purge_before: datetime, current_run_id: int
) -> StatementLambdaElement:
    """Delete recorder_runs rows."""
    return lambda_stmt(
        lambda: delete(RecorderRuns)
        .filter(RecorderRuns.start < purge_before)
        .filter(RecorderRuns.run_id != current_run_id)
        .execution_options(synchronize_session=False)
    )


def find_events_to_purge(purge_before: float) -> StatementLambdaElement:
    """Find events to purge."""
    return lambda_stmt(
        lambda: select(Events.event_id, Events.data_id)
        .filter(Events.time_fired_ts < purge_before)
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_states_to_purge(purge_before: float) -> StatementLambdaElement:
    """Find states to purge."""
    return lambda_stmt(
        lambda: select(States.state_id, States.attributes_id)
        .filter(States.last_updated_ts < purge_before)
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_short_term_statistics_to_purge(
    purge_before: datetime,
) -> StatementLambdaElement:
    """Find short term statistics to purge."""
    purge_before_ts = purge_before.timestamp()
    return lambda_stmt(
        lambda: select(StatisticsShortTerm.id)
        .filter(StatisticsShortTerm.start_ts < purge_before_ts)
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_statistics_runs_to_purge(
    purge_before: datetime,
) -> StatementLambdaElement:
    """Find statistics_runs to purge."""
    return lambda_stmt(
        lambda: select(StatisticsRuns.run_id)
        .filter(StatisticsRuns.start < purge_before)
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_latest_statistics_runs_run_id() -> StatementLambdaElement:
    """Find the latest statistics_runs run_id."""
    return lambda_stmt(lambda: select(func.max(StatisticsRuns.run_id)))


def find_legacy_event_state_and_attributes_and_data_ids_to_purge(
    purge_before: float,
) -> StatementLambdaElement:
    """Find the latest row in the legacy format to purge."""
    return lambda_stmt(
        lambda: select(
            Events.event_id, Events.data_id, States.state_id, States.attributes_id
        )
        .outerjoin(States, Events.event_id == States.event_id)
        .filter(Events.time_fired_ts < purge_before)
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_legacy_detached_states_and_attributes_to_purge(
    purge_before: float,
) -> StatementLambdaElement:
    """Find states rows with event_id set but not linked event_id in Events."""
    return lambda_stmt(
        lambda: select(States.state_id, States.attributes_id)
        .outerjoin(Events, States.event_id == Events.event_id)
        .filter(States.event_id.isnot(None))
        .filter(
            (States.last_updated_ts < purge_before) | States.last_updated_ts.is_(None)
        )
        .filter(Events.event_id.is_(None))
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_legacy_row() -> StatementLambdaElement:
    """Check if there are still states in the table with an event_id."""
    return lambda_stmt(lambda: select(func.max(States.event_id)))


def find_events_context_ids_to_migrate() -> StatementLambdaElement:
    """Find events context_ids to migrate."""
    return lambda_stmt(
        lambda: select(
            Events.event_id,
            Events.time_fired_ts,
            Events.context_id,
            Events.context_user_id,
            Events.context_parent_id,
        )
        .filter(Events.context_id_bin.is_(None))
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_event_type_to_migrate() -> StatementLambdaElement:
    """Find events event_type to migrate."""
    return lambda_stmt(
        lambda: select(
            Events.event_id,
            Events.event_type,
        )
        .filter(Events.event_type_id.is_(None))
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_entity_ids_to_migrate() -> StatementLambdaElement:
    """Find entity_id to migrate."""
    return lambda_stmt(
        lambda: select(
            States.state_id,
            States.entity_id,
        )
        .filter(States.metadata_id.is_(None))
        .limit(SQLITE_MAX_BIND_VARS)
    )


def batch_cleanup_entity_ids() -> StatementLambdaElement:
    """Find entity_id to cleanup."""
    # Self join because This version of MariaDB doesn't yet support 'LIMIT & IN/ALL/ANY/SOME subquery'
    return lambda_stmt(
        lambda: update(States)
        .where(
            States.state_id.in_(
                select(States.state_id)
                .join(
                    states_with_entity_ids := select(
                        States.state_id.label("state_id_with_entity_id")
                    )
                    .filter(States.entity_id.is_not(None))
                    .limit(5000)
                    .subquery(),
                    States.state_id == states_with_entity_ids.c.state_id_with_entity_id,
                )
                .alias("states_with_entity_ids")
                .select()
            )
        )
        .values(entity_id=None)
    )


def has_used_states_event_ids() -> StatementLambdaElement:
    """Check if there are used event_ids in the states table."""
    return lambda_stmt(
        lambda: select(States.state_id).filter(States.event_id.isnot(None)).limit(1)
    )


def has_events_context_ids_to_migrate() -> StatementLambdaElement:
    """Check if there are events context ids to migrate."""
    return lambda_stmt(
        lambda: select(Events.event_id).filter(Events.context_id_bin.is_(None)).limit(1)
    )


def has_states_context_ids_to_migrate() -> StatementLambdaElement:
    """Check if there are states context ids to migrate."""
    return lambda_stmt(
        lambda: select(States.state_id).filter(States.context_id_bin.is_(None)).limit(1)
    )


def has_event_type_to_migrate() -> StatementLambdaElement:
    """Check if there are event_types to migrate."""
    return lambda_stmt(
        lambda: select(Events.event_id).filter(Events.event_type_id.is_(None)).limit(1)
    )


def has_entity_ids_to_migrate() -> StatementLambdaElement:
    """Check if there are entity_id to migrate."""
    return lambda_stmt(
        lambda: select(States.state_id).filter(States.metadata_id.is_(None)).limit(1)
    )


def find_states_context_ids_to_migrate() -> StatementLambdaElement:
    """Find events context_ids to migrate."""
    return lambda_stmt(
        lambda: select(
            States.state_id,
            States.last_updated_ts,
            States.context_id,
            States.context_user_id,
            States.context_parent_id,
        )
        .filter(States.context_id_bin.is_(None))
        .limit(SQLITE_MAX_BIND_VARS)
    )


def find_event_types_to_purge() -> StatementLambdaElement:
    """Find event_type_ids to purge."""
    return lambda_stmt(
        lambda: select(EventTypes.event_type_id, EventTypes.event_type).where(
            EventTypes.event_type_id.not_in(
                select(EventTypes.event_type_id).join(
                    used_event_type_ids := select(
                        distinct(Events.event_type_id).label("used_event_type_id")
                    ).subquery(),
                    EventTypes.event_type_id
                    == used_event_type_ids.c.used_event_type_id,
                )
            )
        )
    )


def find_entity_ids_to_purge() -> StatementLambdaElement:
    """Find entity_ids to purge."""
    return lambda_stmt(
        lambda: select(StatesMeta.metadata_id, StatesMeta.entity_id).where(
            StatesMeta.metadata_id.not_in(
                select(StatesMeta.metadata_id).join(
                    used_states_metadata_id := select(
                        distinct(States.metadata_id).label("used_states_metadata_id")
                    ).subquery(),
                    StatesMeta.metadata_id
                    == used_states_metadata_id.c.used_states_metadata_id,
                )
            )
        )
    )


def delete_event_types_rows(event_type_ids: Iterable[int]) -> StatementLambdaElement:
    """Delete EventTypes rows."""
    return lambda_stmt(
        lambda: delete(EventTypes)
        .where(EventTypes.event_type_id.in_(event_type_ids))
        .execution_options(synchronize_session=False)
    )


def delete_states_meta_rows(metadata_ids: Iterable[int]) -> StatementLambdaElement:
    """Delete StatesMeta rows."""
    return lambda_stmt(
        lambda: delete(StatesMeta)
        .where(StatesMeta.metadata_id.in_(metadata_ids))
        .execution_options(synchronize_session=False)
    )
