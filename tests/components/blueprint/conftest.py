"""Blueprints conftest."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def stub_blueprint_populate():
    """Stub copying the blueprints to the config folder."""
    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints.async_populate"
    ):
        yield
