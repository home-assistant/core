"""Fixtures for the number entity component tests."""

import pytest

from .common import MockNumberEntity

UNIQUE_NUMBER = "unique_number"


@pytest.fixture
def mock_number_entities() -> list[MockNumberEntity]:
    """Return a list of mock number entities."""
    return [
        MockNumberEntity(
            name="test",
            unique_id="unique_number",
            native_value=50.0,
        ),
    ]
