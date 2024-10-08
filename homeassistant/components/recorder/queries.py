"""Queries for the recorder."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import delete, distinct, func, lambda_stmt, select, union_all, update
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Select

from .db_schema import (
    EventData,
    Events,
    EventTypes,
    MigrationChanges,
    RecorderRuns,
    StateAttributes,
    States,
    StatesMeta,
    Statistics,
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
    """Delete event rows."""
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


def find_events_to_purge(
    purge_before: float, max_bind_vars: int
) -> StatementLambdaElement:
    """Find events to purge."""
    return lambda_stmt(
        lambda: select(Events.event_id, Events.data_id)
        .filter(Events.time_fired_ts < purge_before)
        .limit(max_bind_vars)
    )


def find_states_to_purge(
    purge_before: float, max_bind_vars: int
) -> StatementLambdaElement:
    """Find states to purge."""
    return lambda_stmt(
        lambda: select(States.state_id, States.attributes_id)
        .filter(States.last_updated_ts < purge_before)
        .limit(max_bind_vars)
    )


def find_short_term_statistics_to_purge(
    purge_before: datetime, max_bind_vars: int
) -> StatementLambdaElement:
    """Find short term statistics to purge."""
    purge_before_ts = purge_before.timestamp()
    return lambda_stmt(
        lambda: select(StatisticsShortTerm.id)
        .filter(StatisticsShortTerm.start_ts < purge_before_ts)
        .limit(max_bind_vars)
    )


def find_statistics_runs_to_purge(
    purge_before: datetime, max_bind_vars: int
) -> StatementLambdaElement:
    """Find statistics_runs to purge."""
    return lambda_stmt(
        lambda: select(StatisticsRuns.run_id)
        .filter(StatisticsRuns.start < purge_before)
        .limit(max_bind_vars)
    )


def find_latest_statistics_runs_run_id() -> StatementLambdaElement:
    """Find the latest statistics_runs run_id."""
    return lambda_stmt(lambda: select(func.max(StatisticsRuns.run_id)))


def find_legacy_event_state_and_attributes_and_data_ids_to_purge(
    purge_before: float, max_bind_vars: int
) -> StatementLambdaElement:
    """Find the latest row in the legacy format to purge."""
    return lambda_stmt(
        lambda: select(
            Events.event_id, Events.data_id, States.state_id, States.attributes_id
        )
        .outerjoin(States, Events.event_id == States.event_id)
        .filter(Events.time_fired_ts < purge_before)
        .limit(max_bind_vars)
    )


def find_legacy_detached_states_and_attributes_to_purge(
    purge_before: float, max_bind_vars: int
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
        .limit(max_bind_vars)
    )


def find_legacy_row() -> StatementLambdaElement:
    """Check if there are still states in the table with an event_id."""
    return lambda_stmt(lambda: select(func.max(States.event_id)))


def find_events_context_ids_to_migrate(max_bind_vars: int) -> StatementLambdaElement:
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
        .limit(max_bind_vars)
    )


def find_event_type_to_migrate(max_bind_vars: int) -> StatementLambdaElement:
    """Find events event_type to migrate."""
    return lambda_stmt(
        lambda: select(
            Events.event_id,
            Events.event_type,
        )
        .filter(Events.event_type_id.is_(None))
        .limit(max_bind_vars)
    )


def find_entity_ids_to_migrate(max_bind_vars: int) -> StatementLambdaElement:
    """Find entity_id to migrate."""
    return lambda_stmt(
        lambda: select(
            States.state_id,
            States.entity_id,
        )
        .filter(States.metadata_id.is_(None))
        .limit(max_bind_vars)
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


def has_used_states_entity_ids() -> StatementLambdaElement:
    """Check if there are used entity_ids in the states table."""
    return lambda_stmt(
        lambda: select(States.state_id).filter(States.entity_id.isnot(None)).limit(1)
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


def find_states_context_ids_to_migrate(max_bind_vars: int) -> StatementLambdaElement:
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
        .limit(max_bind_vars)
    )


def get_migration_changes() -> StatementLambdaElement:
    """Query the database for previous migration changes."""
    return lambda_stmt(
        lambda: select(MigrationChanges.migration_id, MigrationChanges.version)
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


def find_unmigrated_short_term_statistics_rows(
    max_bind_vars: int,
) -> StatementLambdaElement:
    """Find unmigrated short term statistics rows."""
    return lambda_stmt(
        lambda: select(
            StatisticsShortTerm.id,
            StatisticsShortTerm.start,
            StatisticsShortTerm.created,
            StatisticsShortTerm.last_reset,
        )
        .filter(StatisticsShortTerm.start_ts.is_(None))
        .filter(StatisticsShortTerm.start.isnot(None))
        .limit(max_bind_vars)
    )


def find_unmigrated_statistics_rows(max_bind_vars: int) -> StatementLambdaElement:
    """Find unmigrated statistics rows."""
    return lambda_stmt(
        lambda: select(
            Statistics.id, Statistics.start, Statistics.created, Statistics.last_reset
        )
        .filter(Statistics.start_ts.is_(None))
        .filter(Statistics.start.isnot(None))
        .limit(max_bind_vars)
    )


def migrate_single_short_term_statistics_row_to_timestamp(
    statistic_id: int,
    start_ts: float | None,
    created_ts: float | None,
    last_reset_ts: float | None,
) -> StatementLambdaElement:
    """Migrate a single short term statistics row to timestamp."""
    return lambda_stmt(
        lambda: update(StatisticsShortTerm)
        .where(StatisticsShortTerm.id == statistic_id)
        .values(
            start_ts=start_ts,
            start=None,
            created_ts=created_ts,
            created=None,
            last_reset_ts=last_reset_ts,
            last_reset=None,
        )
        .execution_options(synchronize_session=False)
    )


def migrate_single_statistics_row_to_timestamp(
    statistic_id: int,
    start_ts: float | None,
    created_ts: float | None,
    last_reset_ts: float | None,
) -> StatementLambdaElement:
    """Migrate a single statistics row to timestamp."""
    return lambda_stmt(
        lambda: update(Statistics)
        .where(Statistics.id == statistic_id)
        .values(
            start_ts=start_ts,
            start=None,
            created_ts=created_ts,
            created=None,
            last_reset_ts=last_reset_ts,
            last_reset=None,
        )
        .execution_options(synchronize_session=False)
    )


def delete_duplicate_short_term_statistics_row(
    statistic_id: int,
) -> StatementLambdaElement:
    """Delete a single duplicate short term statistics row."""
    return lambda_stmt(
        lambda: delete(StatisticsShortTerm)
        .where(StatisticsShortTerm.id == statistic_id)
        .execution_options(synchronize_session=False)
    )


def delete_duplicate_statistics_row(statistic_id: int) -> StatementLambdaElement:
    """Delete a single duplicate statistics row."""
    return lambda_stmt(
        lambda: delete(Statistics)
        .where(Statistics.id == statistic_id)
        .execution_options(synchronize_session=False)
    )
