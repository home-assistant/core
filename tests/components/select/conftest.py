"""Fixtures for the select entity component tests."""

import pytest

from .common import MockSelectEntity


@pytest.fixture
def mock_select_entities() -> list[MockSelectEntity]:
    """Return a list of mock select entities."""
    return [
        MockSelectEntity(
            name="select 1",
            unique_id="unique_select_1",
            options=["option 1", "option 2", "option 3"],
            current_option="option 1",
        ),
        MockSelectEntity(
            name="select 2",
            unique_id="unique_select_2",
            options=["option 1", "option 2", "option 3"],
            current_option=None,
        ),
    ]
