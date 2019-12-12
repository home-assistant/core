"""Fixtures for tests."""

from mock import patch
import pytest

from .common import ComponentFactory


@pytest.fixture()
def vera_component_factory():
    """Return a factory for initializing the vera component."""
    with patch("pyvera.init_controller") as init_controller_mock:
        yield ComponentFactory(init_controller_mock)
