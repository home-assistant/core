"""Blueprints test helpers."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch


def stub_blueprint_populate_fixture_helper() -> Generator[None, Any, None]:
    """Stub copying the blueprints to the config folder."""
    with patch(
        "homeassistant.components.blueprint.models.DomainBlueprints.async_populate"
    ):
        yield
