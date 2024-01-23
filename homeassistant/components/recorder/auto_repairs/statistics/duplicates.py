"""Statistics duplication repairs."""
from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.engine.row import Row
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import literal_column

from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util import dt as dt_util

from ...const import SQLITE_MAX_BIND_VARS
from ...db_schema import Statistics, StatisticsBase, StatisticsMeta, StatisticsShortTerm
from ...util import database_job_retry_wrapper, execute

if TYPE_CHECKING:
    from ... import Recorder

_LOGGER = logging.getLogger(__name__)


def _find_duplicates(
    session: Session, table: type[StatisticsBase]
) -> tuple[list[int], list[dict]]:
    """Find duplicated statistics."""
    subquery = (
        session.query(
            table.start,
            table.metadata_id,
            literal_column("1").label("is_duplicate"),
        )
        .group_by(table.metadata_id, table.start)
        .having(func.count() > 1)
        .subquery()
    )
    query = (
        session.query(
            table.id,
            table.metadata_id,
            table.created,
            table.start,
            table.mean,
            table.min,
            table.max,
            table.last_reset,
            table.state,
            table.sum,
        )
        .outerjoin(
            subquery,
            (subquery.c.metadata_id == table.metadata_id)
            & (subquery.c.start == table.start),
        )
        .filter(subquery.c.is_duplicate == 1)
        .order_by(table.metadata_id, table.start, table.id.desc())
        .limit(1000 * SQLITE_MAX_BIND_VARS)
    )
    duplicates = execute(query)
    original_as_dict = {}
    start = None
    metadata_id = None
    duplicate_ids: list[int] = []
    non_identical_duplicates_as_dict: list[dict] = []

    if not duplicates:
        return (duplicate_ids, non_identical_duplicates_as_dict)

    def columns_to_dict(duplicate: Row) -> dict:
        """Convert a SQLAlchemy row to dict."""
        dict_ = {}
        for key in (
            "id",
            "metadata_id",
            "start",
            "created",
            "mean",
            "min",
            "max",
            "last_reset",
            "state",
            "sum",
        ):
            dict_[key] = getattr(duplicate, key)
        return dict_

    def compare_statistic_rows(row1: dict, row2: dict) -> bool:
        """Compare two statistics rows, ignoring id and created."""
        ignore_keys = {"id", "created"}
        keys1 = set(row1).difference(ignore_keys)
        keys2 = set(row2).difference(ignore_keys)
        return keys1 == keys2 and all(row1[k] == row2[k] for k in keys1)

    for duplicate in duplicates:
        if start != duplicate.start or metadata_id != duplicate.metadata_id:
            original_as_dict = columns_to_dict(duplicate)
            start = duplicate.start
            metadata_id = duplicate.metadata_id
            continue
        duplicate_as_dict = columns_to_dict(duplicate)
        duplicate_ids.append(duplicate.id)
        if not compare_statistic_rows(original_as_dict, duplicate_as_dict):
            non_identical_duplicates_as_dict.append(
                {"duplicate": duplicate_as_dict, "original": original_as_dict}
            )

    return (duplicate_ids, non_identical_duplicates_as_dict)


def _delete_duplicates_from_table(
    session: Session, table: type[StatisticsBase]
) -> tuple[int, list[dict]]:
    """Identify and delete duplicated statistics from a specified table."""
    all_non_identical_duplicates: list[dict] = []
    total_deleted_rows = 0
    while True:
        duplicate_ids, non_identical_duplicates = _find_duplicates(session, table)
        if not duplicate_ids:
            break
        all_non_identical_duplicates.extend(non_identical_duplicates)
        for i in range(0, len(duplicate_ids), SQLITE_MAX_BIND_VARS):
            deleted_rows = (
                session.query(table)
                .filter(table.id.in_(duplicate_ids[i : i + SQLITE_MAX_BIND_VARS]))
                .delete(synchronize_session=False)
            )
            total_deleted_rows += deleted_rows
    return (total_deleted_rows, all_non_identical_duplicates)


@database_job_retry_wrapper("delete statistics duplicates", 3)
def delete_statistics_duplicates(
    instance: Recorder, hass: HomeAssistant, session: Session
) -> None:
    """Identify and delete duplicated statistics.

    A backup will be made of duplicated statistics before it is deleted.
    """
    deleted_statistics_rows, non_identical_duplicates = _delete_duplicates_from_table(
        session, Statistics
    )
    if deleted_statistics_rows:
        _LOGGER.info("Deleted %s duplicated statistics rows", deleted_statistics_rows)

    if non_identical_duplicates:
        isotime = dt_util.utcnow().isoformat()
        backup_file_name = f"deleted_statistics.{isotime}.json"
        backup_path = hass.config.path(STORAGE_DIR, backup_file_name)

        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        with open(backup_path, "w", encoding="utf8") as backup_file:
            json.dump(
                non_identical_duplicates,
                backup_file,
                indent=4,
                sort_keys=True,
                cls=JSONEncoder,
            )
        _LOGGER.warning(
            (
                "Deleted %s non identical duplicated %s rows, a backup of the deleted"
                " rows has been saved to %s"
            ),
            len(non_identical_duplicates),
            Statistics.__tablename__,
            backup_path,
        )

    deleted_short_term_statistics_rows, _ = _delete_duplicates_from_table(
        session, StatisticsShortTerm
    )
    if deleted_short_term_statistics_rows:
        _LOGGER.warning(
            "Deleted duplicated short term statistic rows, please report at %s",
            "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+recorder%22",
        )


def _find_statistics_meta_duplicates(session: Session) -> list[int]:
    """Find duplicated statistics_meta."""
    # When querying the database, be careful to only explicitly query for columns
    # which were present in schema version 29. If querying the table, SQLAlchemy
    # will refer to future columns.
    subquery = (
        session.query(
            StatisticsMeta.statistic_id,
            literal_column("1").label("is_duplicate"),
        )
        .group_by(StatisticsMeta.statistic_id)
        .having(func.count() > 1)
        .subquery()
    )
    query = (
        session.query(StatisticsMeta.statistic_id, StatisticsMeta.id)
        .outerjoin(
            subquery,
            (subquery.c.statistic_id == StatisticsMeta.statistic_id),
        )
        .filter(subquery.c.is_duplicate == 1)
        .order_by(StatisticsMeta.statistic_id, StatisticsMeta.id.desc())
        .limit(1000 * SQLITE_MAX_BIND_VARS)
    )
    duplicates = execute(query)
    statistic_id = None
    duplicate_ids: list[int] = []

    if not duplicates:
        return duplicate_ids

    for duplicate in duplicates:
        if statistic_id != duplicate.statistic_id:
            statistic_id = duplicate.statistic_id
            continue
        duplicate_ids.append(duplicate.id)

    return duplicate_ids


def _delete_statistics_meta_duplicates(session: Session) -> int:
    """Identify and delete duplicated statistics from a specified table."""
    total_deleted_rows = 0
    while True:
        duplicate_ids = _find_statistics_meta_duplicates(session)
        if not duplicate_ids:
            break
        for i in range(0, len(duplicate_ids), SQLITE_MAX_BIND_VARS):
            deleted_rows = (
                session.query(StatisticsMeta)
                .filter(
                    StatisticsMeta.id.in_(duplicate_ids[i : i + SQLITE_MAX_BIND_VARS])
                )
                .delete(synchronize_session=False)
            )
            total_deleted_rows += deleted_rows
    return total_deleted_rows


@database_job_retry_wrapper("delete statistics meta duplicates", 3)
def delete_statistics_meta_duplicates(instance: Recorder, session: Session) -> None:
    """Identify and delete duplicated statistics_meta.

    This is used when migrating from schema version 28 to schema version 29.
    """
    deleted_statistics_rows = _delete_statistics_meta_duplicates(session)
    if deleted_statistics_rows:
        statistics_meta_manager = instance.statistics_meta_manager
        statistics_meta_manager.reset()
        statistics_meta_manager.load(session)
        _LOGGER.info(
            "Deleted %s duplicated statistics_meta rows", deleted_statistics_rows
        )
