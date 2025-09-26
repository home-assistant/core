"""Fixtures for Garages Amsterdam integration tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from odp_amsterdam import Garage, GarageCategory, VehicleType
import pytest

from homeassistant.components.garages_amsterdam.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override setup entry."""
    with patch(
        "homeassistant.components.garages_amsterdam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_garages_amsterdam() -> Generator[AsyncMock]:
    """Mock garages_amsterdam garages."""
    with (
        patch(
            "homeassistant.components.garages_amsterdam.ODPAmsterdam",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.garages_amsterdam.config_flow.ODPAmsterdam",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.all_garages.return_value = [
            Garage(
                garage_id="test-id-1",
                garage_name="IJDok",
                vehicle=VehicleType.CAR,
                category=GarageCategory.GARAGE,
                state="ok",
                free_space_short=100,
                free_space_long=10,
                short_capacity=120,
                long_capacity=60,
                availability_pct=50.5,
                longitude=1.111111,
                latitude=2.222222,
                updated_at=datetime(2023, 2, 23, 13, 44, 48, tzinfo=UTC),
            ),
            Garage(
                garage_id="test-id-2",
                garage_name="Arena",
                vehicle=VehicleType.CAR,
                category=GarageCategory.GARAGE,
                state="error",
                free_space_short=200,
                free_space_long=None,
                short_capacity=240,
                long_capacity=None,
                availability_pct=83.3,
                longitude=3.333333,
                latitude=4.444444,
                updated_at=datetime(2023, 2, 23, 13, 44, 48, tzinfo=UTC),
            ),
        ]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="monitor",
        domain=DOMAIN,
        data={
            "garage_name": "IJDok",
        },
        unique_id="unique_thingy",
        version=1,
    )
