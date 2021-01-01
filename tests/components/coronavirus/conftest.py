"""Test helpers."""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_cases():
    """Mock coronavirus cases."""
    with patch(
        "coronavirus.get_cases",
        return_value=[
            Mock(country="Netherlands", confirmed=10, recovered=8, deaths=1, current=1),
            Mock(country="Germany", confirmed=1, recovered=0, deaths=0, current=0),
            Mock(
                country="Sweden",
                confirmed=None,
                recovered=None,
                deaths=None,
                current=None,
            ),
        ],
    ) as mock_get_cases:
        yield mock_get_cases
