"""Test fixtures for mqtt component."""

import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate):
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(autouse=True)
def patch_hass_config(mock_hass_config: None) -> None:
    """Patch configuration.yaml."""
