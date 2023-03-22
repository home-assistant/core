"""Fixtures for tests."""
from unittest.mock import patch

import pytest

from .common import ComponentFactory

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def vera_component_factory():
    """Return a factory for initializing the vera component."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        yield ComponentFactory(vera_controller_class_mock)
