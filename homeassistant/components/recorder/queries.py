"""Queries for the recorder."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import and_, delete, distinct, func, lambda_stmt, select, update
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
    attributes_ids: Iterable[int],
) -> StatementLambdaElement:
    """Find attributes ids that exist in the states table.

    PostgreSQL does not support skip/loose index scan
    https://wiki.postgresql.org/wiki/Loose_indexscan

    To avoid using distinct, we use a subquery to get the latest last_updated_ts
    for each attributes_id. This is then used to filter out the attributes_id
    that no longer exist in the States table.

    This query is fast for older MariaDB, older MySQL, and PostgreSQL.
    """
    return lambda_stmt(
        lambda: select(StateAttributes.attributes_id)
        .select_from(StateAttributes)
        .join(
            States,
            and_(
                States.attributes_id == StateAttributes.attributes_id,
                States.last_updated_ts
                == select(States.last_updated_ts)
                .where(States.attributes_id == StateAttributes.attributes_id)
                .limit(1)
                .scalar_subquery()
                .correlate(StateAttributes),
            ),
        )
        .where(StateAttributes.attributes_id.in_(attributes_ids))
    )


def data_ids_exist_in_events_with_fast_in_distinct(
    data_ids: Iterable[int],
) -> StatementLambdaElement:
    """Find data ids that exist in the events table."""
    return lambda_stmt(
        lambda: select(distinct(Events.data_id)).filter(Events.data_id.in_(data_ids))
    )


def data_ids_exist_in_events(
    data_ids: Iterable[int],
) -> StatementLambdaElement:
    """Find data ids that exist in the events table.

    PostgreSQL does not support skip/loose index scan
    https://wiki.postgresql.org/wiki/Loose_indexscan

    To avoid using distinct, we use a subquery to get the latest time_fired_ts
    for each data_id. This is then used to filter out the data_id
    that no longer exist in the Events table.

    This query is fast for older MariaDB, older MySQL, and PostgreSQL.
    """
    return lambda_stmt(
        lambda: select(EventData.data_id)
        .select_from(EventData)
        .join(
            Events,
            and_(
                Events.data_id == EventData.data_id,
                Events.time_fired_ts
                == select(Events.time_fired_ts)
                .where(Events.data_id == EventData.data_id)
                .limit(1)
                .scalar_subquery()
                .correlate(EventData),
            ),
        )
        .where(EventData.data_id.in_(data_ids))
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
        .filter(RecorderRuns.end.is_not(None))
        .filter(RecorderRuns.end < purge_before)
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


def find_oldest_state() -> StatementLambdaElement:
    """Find the last_updated_ts of the oldest state."""
    return lambda_stmt(
        lambda: select(States.last_updated_ts)
        .order_by(States.last_updated_ts.asc())
        .limit(1)
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
    """Find event_type_ids to purge.

    PostgreSQL does not support skip/loose index scan
    https://wiki.postgresql.org/wiki/Loose_indexscan

    To avoid using distinct, we use a subquery to get the latest time_fired_ts
    for each event_type. This is then used to filter out the event_type_ids
    that no longer exist in the Events table.

    This query is fast for SQLite, MariaDB, MySQL, and PostgreSQL.
    """
    return lambda_stmt(
        lambda: select(EventTypes.event_type_id, EventTypes.event_type).where(
            EventTypes.event_type_id.not_in(
                select(EventTypes.event_type_id)
                .select_from(EventTypes)
                .join(
                    Events,
                    and_(
                        EventTypes.event_type_id == Events.event_type_id,
                        Events.time_fired_ts
                        == select(Events.time_fired_ts)
                        .where(Events.event_type_id == EventTypes.event_type_id)
                        .limit(1)
                        .scalar_subquery()
                        .correlate(EventTypes),
                    ),
                )
            )
        )
    )


def find_entity_ids_to_purge() -> StatementLambdaElement:
    """Find metadata_ids for each entity_id to purge.

    PostgreSQL does not support skip/loose index scan
    https://wiki.postgresql.org/wiki/Loose_indexscan

    To avoid using distinct, we use a subquery to get the latest last_updated_ts
    for each entity_id. This is then used to filter out the metadata_ids
    that no longer exist in the States table.

    This query is fast for SQLite, MariaDB, MySQL, and PostgreSQL.
    """
    return lambda_stmt(
        lambda: select(StatesMeta.metadata_id, StatesMeta.entity_id).where(
            StatesMeta.metadata_id.not_in(
                select(StatesMeta.metadata_id)
                .select_from(StatesMeta)
                .join(
                    States,
                    and_(
                        StatesMeta.metadata_id == States.metadata_id,
                        States.last_updated_ts
                        == select(States.last_updated_ts)
                        .where(States.metadata_id == StatesMeta.metadata_id)
                        .limit(1)
                        .scalar_subquery()
                        .correlate(StatesMeta),
                    ),
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
