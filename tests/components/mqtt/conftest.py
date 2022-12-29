"""Test fixtures for mqtt component."""
import logging

from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401
from tests.components.light.conftest import mock_light_profiles  # noqa: F401

logging.basicConfig(level=logging.DEBUG)
