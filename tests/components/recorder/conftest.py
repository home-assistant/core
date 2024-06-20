"""Fixtures for the recorder component tests."""

from unittest.mock import patch

import pytest
from typing_extensions import Generator

from homeassistant.components import recorder
from homeassistant.core import HomeAssistant


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
