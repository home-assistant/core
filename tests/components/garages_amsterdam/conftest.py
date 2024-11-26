"""Fixtures for Garages Amsterdam integration tests."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.garages_amsterdam.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="monitor",
        domain=DOMAIN,
        data={},
        unique_id="unique_thingy",
        version=1,
    )


@pytest.fixture(autouse=True)
def mock_garages_amsterdam():
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
