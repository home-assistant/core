"""Common fixtures for the Škoda tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
from skoda_public_api.models.vehicle import VehicleResponse

from homeassistant.components.skoda.const import CONF_VIN, DOMAIN
from homeassistant.const import CONF_API_KEY

VIN = "TMBJM7NP2M1TMP511"
API_KEY = "test-api-key"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.skoda.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Škoda config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Škoda Enyaq Coupé",
        unique_id=VIN,
        data={CONF_VIN: VIN, CONF_API_KEY: API_KEY},
    )


@pytest.fixture
def vehicle_fixture() -> str:
    """Return the name of the vehicle response fixture to load."""
    return "vehicle_electric.json"


@pytest.fixture
def mock_skoda_client(vehicle_fixture: str) -> Generator[AsyncMock]:
    """Mock the Škoda OpenAPI client."""
    with (
        patch(
            "homeassistant.components.skoda.OpenAPIClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.skoda.config_flow.OpenAPIClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_vehicle.return_value = VehicleResponse.model_validate(
            load_json_object_fixture(vehicle_fixture, DOMAIN)
        )
        yield client
