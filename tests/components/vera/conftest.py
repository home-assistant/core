"""Fixtures for tests."""

from mock import patch
import pytest

from .common import ComponentFactory


@pytest.fixture()
def vera_component_factory():
    """Return a factory for initializing the vera component."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        yield ComponentFactory(vera_controller_class_mock)
