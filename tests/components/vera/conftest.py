"""Fixtures for tests."""

import pytest

from .common import ComponentFactory

from tests.async_mock import patch


@pytest.fixture()
def vera_component_factory():
    """Return a factory for initializing the vera component."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        yield ComponentFactory(vera_controller_class_mock)
