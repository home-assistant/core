"""Test helpers."""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_cases():
    """Mock garages_amsterdam garages."""
    with patch(
        "odp_amsterdam.ODPAmsterdam.all_garages",
        return_value=[
            Mock(
                garage_name="IJDok",
                free_space_short=100,
                free_space_long=10,
                short_capacity=120,
                long_capacity=60,
                state="ok",
            ),
            Mock(
                garage_name="Arena",
                free_space_short=200,
                free_space_long=20,
                short_capacity=240,
                long_capacity=80,
                state="error",
            ),
        ],
    ) as mock_get_garages:
        yield mock_get_garages
