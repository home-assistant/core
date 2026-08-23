"""AirGradient tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.airgradient.const import DOMAIN
from homeassistant.const import CONF_HOST

from . import load_config_fixture, load_measures_fixture

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airgradient.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_airgradient_client() -> Generator[AsyncMock]:
    """Mock an AirGradient client."""
    with (
        patch(
            "homeassistant.components.airgradient.AirGradientClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.airgradient.config_flow.AirGradientClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.host = "10.0.0.131"
        client.get_current_measures.return_value = load_measures_fixture(
            "current_measures_indoor.json"
        )
        client.get_config.return_value = load_config_fixture("get_config_local.json")
        client.get_latest_firmware_version.return_value = "3.1.4"
        yield client


@pytest.fixture(params=["indoor", "outdoor"])
def airgradient_devices(
    mock_airgradient_client: AsyncMock, request: pytest.FixtureRequest
) -> Generator[AsyncMock]:
    """Return a list of AirGradient devices."""
    mock_airgradient_client.get_current_measures.return_value = load_measures_fixture(
        f"current_measures_{request.param}.json"
    )
    return mock_airgradient_client


@pytest.fixture
def mock_new_airgradient_client(
    mock_airgradient_client: AsyncMock,
) -> AsyncMock:
    """Mock a new AirGradient client."""
    mock_airgradient_client.get_config.return_value = load_config_fixture(
        "get_config.json"
    )
    return mock_airgradient_client


@pytest.fixture
def mock_cloud_airgradient_client(
    mock_airgradient_client: AsyncMock,
) -> AsyncMock:
    """Mock a cloud AirGradient client."""
    mock_airgradient_client.get_config.return_value = load_config_fixture(
        "get_config_cloud.json"
    )
    return mock_airgradient_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Airgradient",
        data={CONF_HOST: "10.0.0.131"},
        unique_id="84fce612f5b8",
    )
