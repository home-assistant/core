"""Fixtures for the recorder component tests."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
import threading
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder import db_schema
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

    migration_done: threading.Event
    migration_stall: threading.Event
    migration_started: threading.Event
    migration_version: int | None
    apply_update_mock: Mock


@pytest.fixture
async def instrument_migration(
    hass: HomeAssistant,
) -> AsyncGenerator[InstrumentedMigration]:
    """Instrument recorder migration."""

    real_migrate_schema = recorder.migration.migrate_schema
    real_apply_update = recorder.migration._apply_update

    def _instrument_migrate_schema(*args):
        """Control migration progress and check results."""
        instrumented_migration.migration_started.set()

        try:
            real_migrate_schema(*args)
        except Exception:
            instrumented_migration.migration_done.set()
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
        instrumented_migration.migration_done.set()

    def _instrument_apply_update(*args):
        """Control migration progress."""
        instrumented_migration.migration_stall.wait()
        real_apply_update(*args)

    with (
        patch(
            "homeassistant.components.recorder.migration.migrate_schema",
            wraps=_instrument_migrate_schema,
        ),
        patch(
            "homeassistant.components.recorder.migration._apply_update",
            wraps=_instrument_apply_update,
        ) as apply_update_mock,
    ):
        instrumented_migration = InstrumentedMigration(
            migration_done=threading.Event(),
            migration_stall=threading.Event(),
            migration_started=threading.Event(),
            migration_version=None,
            apply_update_mock=apply_update_mock,
        )

        yield instrumented_migration
