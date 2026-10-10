"""Fixtures for BirdNET-Go integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiobirdnetgo import BirdNetGoClient, DashboardKPIs
import pytest

from homeassistant.components.birdnet_go.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_kpis() -> DashboardKPIs:
    """Return mock DashboardKPIs from JSON fixture."""
    return DashboardKPIs.from_dict(load_json_object_fixture("kpis.json", DOMAIN))


@pytest.fixture
def mock_birdnet_client(
    mock_kpis: DashboardKPIs,
) -> Generator[AsyncMock]:
    """Mock BirdNetGoClient."""
    mock_instance = AsyncMock(spec=BirdNetGoClient)
    mock_instance.host = "192.168.1.100"
    mock_instance.port = 8080
    mock_instance.use_ssl = False
    mock_instance.base_url = "http://192.168.1.100:8080"
    mock_instance.get_kpis = AsyncMock(return_value=mock_kpis)

    def _create_client(*args: object, **kwargs: object) -> AsyncMock:
        real_client = BirdNetGoClient(*args, **kwargs)  # type: ignore[arg-type]
        mock_instance.host = real_client.host
        mock_instance.port = real_client.port
        mock_instance.use_ssl = real_client.use_ssl
        mock_instance.base_url = real_client.base_url
        return mock_instance

    with (
        patch(
            "homeassistant.components.birdnet_go.config_flow.BirdNetGoClient",
            side_effect=_create_client,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.birdnet_go.BirdNetGoClient",
            new=mock_client_cls,
        ),
    ):
        mock_client_cls.return_value = mock_instance
        yield mock_instance


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
