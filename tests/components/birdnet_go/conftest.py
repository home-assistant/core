"""Fixtures for BirdNET-Go integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiobirdnetgo import DashboardKPIs, HealthResponse, PingResponse
import pytest

from homeassistant.components.birdnet_go.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_kpis() -> DashboardKPIs:
    """Return mock DashboardKPIs from JSON fixture."""
    return DashboardKPIs.from_dict(load_json_object_fixture("kpis.json", DOMAIN))


@pytest.fixture
def mock_health() -> HealthResponse:
    """Return mock HealthResponse from JSON fixture."""
    return HealthResponse.from_dict(load_json_object_fixture("health.json", DOMAIN))


@pytest.fixture
def mock_birdnet_client(
    mock_kpis: DashboardKPIs, mock_health: HealthResponse
) -> Generator[AsyncMock]:
    """Mock BirdNetGoClient."""
    with (
        patch(
            "homeassistant.components.birdnet_go.config_flow.BirdNetGoClient",
            autospec=True,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.birdnet_go.BirdNetGoClient",
            new=mock_client_cls,
        ),
    ):
        client = mock_client_cls.return_value
        client.host = "192.168.1.100"
        client.port = 8080
        client.use_ssl = False
        client.base_url = "http://192.168.1.100:8080"
        client.ping = AsyncMock(return_value=True)
        client.get_ping = AsyncMock(return_value=PingResponse(status="ok"))
        client.get_health = AsyncMock(return_value=mock_health)
        client.get_kpis = AsyncMock(return_value=mock_kpis)
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return mock ConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="BirdNET-Go (192.168.1.100:8080)",
        unique_id="192.168.1.100:8080",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )
