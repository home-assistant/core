"""Blueprints conftest."""

import pytest


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate):
    """Stub copying the blueprints to the config folder."""
