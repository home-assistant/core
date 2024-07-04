"""Fixtures for the recorder component tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components import recorder
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
