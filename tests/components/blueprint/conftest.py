"""Blueprints conftest."""

import pytest

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def stub_blueprint_populate():
    """Stub copying the blueprint automations to the config folder."""
    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints.async_populate"
    ):
        yield
