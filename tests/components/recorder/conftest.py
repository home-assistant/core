"""Fixtures for the recorder component tests."""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
import threading
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import db_schema
from homeassistant.components.recorder.const import MAX_IDS_FOR_INDEXED_GROUP_BY
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant


def pytest_configure(config):
    """Add custom skip_on_db_engine marker."""
    config.addinivalue_line(
        "markers",
        "skip_on_db_engine(engine): mark test to run only on named DB engine(s)",
    )


@pytest.fixture
def skip_by_db_engine(request: pytest.FixtureRequest, recorder_db_url: str) -> None:
    """Fixture to skip tests on unsupported DB engines.

    Mark the test with @pytest.mark.skip_on_db_engine("mysql") to skip on mysql, or
    @pytest.mark.skip_on_db_engine(["mysql", "sqlite"]) to skip on mysql and sqlite.
    """
    if request.node.get_closest_marker("skip_on_db_engine"):
        skip_on_db_engine = request.node.get_closest_marker("skip_on_db_engine").args[0]
        if isinstance(skip_on_db_engine, str):
            skip_on_db_engine = [skip_on_db_engine]
        db_engine = recorder_db_url.partition("://")[0]
        if db_engine in skip_on_db_engine:
            pytest.skip(f"skipped for DB engine: {db_engine}")


@pytest.fixture
def recorder_dialect_name(hass: HomeAssistant, db_engine: str) -> Generator[None]:
    """Patch the recorder dialect."""
    if instance := hass.data.get(recorder.DATA_INSTANCE):
        instance.__dict__.pop("dialect_name", None)
        with patch.object(instance, "_dialect_name", db_engine):
            yield
            instance.__dict__.pop("dialect_name", None)
    else:
        with patch(
            "homeassistant.components.recorder.Recorder.dialect_name", db_engine
        ):
            yield


@dataclass(slots=True)
class InstrumentedMigration:
    """Container to aid controlling migration progress."""

    live_migration_done: threading.Event
    live_migration_done_stall: threading.Event
    migration_stall: threading.Event
    migration_started: threading.Event
    migration_version: int | None
    non_live_migration_done: threading.Event
    non_live_migration_done_stall: threading.Event
    apply_update_mock: Mock
    stall_on_schema_version: int | None
    apply_update_stalled: threading.Event
    apply_update_version: int | None


@pytest.fixture(name="instrument_migration")
def instrument_migration_fixture(
    hass: HomeAssistant,
) -> Generator[InstrumentedMigration]:
    """Instrument recorder migration."""
    with instrument_migration(hass) as instrumented_migration:
        yield instrumented_migration


@contextmanager
def instrument_migration(
    hass: HomeAssistant,
) -> Generator[InstrumentedMigration]:
    """Instrument recorder migration."""

    real_migrate_schema_live = recorder.migration.migrate_schema_live
    real_migrate_schema_non_live = recorder.migration.migrate_schema_non_live
    real_apply_update = recorder.migration._apply_update

    def _instrument_migrate_schema_live(real_func, *args):
        """Control migration progress and check results."""
        return _instrument_migrate_schema(
            real_func,
            args,
            instrumented_migration.live_migration_done,
            instrumented_migration.live_migration_done_stall,
        )

    def _instrument_migrate_schema_non_live(real_func, *args):
        """Control migration progress and check results."""
        return _instrument_migrate_schema(
            real_func,
            args,
            instrumented_migration.non_live_migration_done,
            instrumented_migration.non_live_migration_done_stall,
        )

    def _instrument_migrate_schema(
        real_func,
        args,
        migration_done: threading.Event,
        migration_done_stall: threading.Event,
    ):
        """Control migration progress and check results."""
        instrumented_migration.migration_started.set()

        try:
            migration_result = real_func(*args)
        except Exception:
            migration_done.set()
            migration_done_stall.wait()
            raise

        # Check and report the outcome of the migration; if migration fails
        # the recorder will silently create a new database.
        with session_scope(hass=hass, read_only=True) as session:
            res = (
                session.query(db_schema.SchemaChanges)
                .order_by(db_schema.SchemaChanges.change_id.desc())
                .first()
            )
            instrumented_migration.migration_version = res.schema_version
        migration_done.set()
        migration_done_stall.wait()
        return migration_result

    def _instrument_apply_update(
        instance: recorder.Recorder,
        hass: HomeAssistant,
        engine: Engine,
        session_maker: Callable[[], Session],
        new_version: int,
        old_version: int,
    ):
        """Control migration progress."""
        instrumented_migration.apply_update_version = new_version
        stall_version = instrumented_migration.stall_on_schema_version
        if stall_version is None or stall_version == new_version:
            instrumented_migration.apply_update_stalled.set()
            instrumented_migration.migration_stall.wait()
        real_apply_update(
            instance, hass, engine, session_maker, new_version, old_version
        )

    with (
        patch(
            "homeassistant.components.recorder.migration.migrate_schema_live",
            wraps=partial(_instrument_migrate_schema_live, real_migrate_schema_live),
        ),
        patch(
            "homeassistant.components.recorder.migration.migrate_schema_non_live",
            wraps=partial(
                _instrument_migrate_schema_non_live, real_migrate_schema_non_live
            ),
        ),
        patch(
            "homeassistant.components.recorder.migration._apply_update",
            wraps=_instrument_apply_update,
        ) as apply_update_mock,
    ):
        instrumented_migration = InstrumentedMigration(
            live_migration_done=threading.Event(),
            live_migration_done_stall=threading.Event(),
            migration_stall=threading.Event(),
            migration_started=threading.Event(),
            migration_version=None,
            non_live_migration_done=threading.Event(),
            non_live_migration_done_stall=threading.Event(),
            apply_update_mock=apply_update_mock,
            stall_on_schema_version=None,
            apply_update_stalled=threading.Event(),
            apply_update_version=None,
        )

        instrumented_migration.live_migration_done_stall.set()
        instrumented_migration.non_live_migration_done_stall.set()
        yield instrumented_migration


@pytest.fixture(params=[1, 2, MAX_IDS_FOR_INDEXED_GROUP_BY])
def ids_for_start_time_chunk_sizes(request: pytest.FixtureRequest) -> int:
    """Fixture to test different chunk sizes for start time query."""
    return request.param
