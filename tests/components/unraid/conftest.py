"""Shared pytest fixtures for Unraid integration tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from unraid_api.models import ServerInfo, SystemMetrics

from homeassistant.components.unraid.const import DOMAIN
from homeassistant.components.unraid.coordinator import UnraidSystemData
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def create_mock_server_info(
    uuid: str | None = "test-uuid-123",
    hostname: str = "tower",
    unraid_version: str = "7.2.0",
    api_version: str = "4.29.2",
) -> ServerInfo:
    """Create a mock ServerInfo object."""
    return ServerInfo(
        uuid=uuid,
        hostname=hostname,
        manufacturer="Lime Technology",
        model=f"Unraid {unraid_version}",
        sw_version=unraid_version,
        hw_version="6.1.0",
        serial_number=None,
        hw_manufacturer="ASUS",
        hw_model="Pro WS",
        os_distro="Unraid",
        os_release=unraid_version,
        os_arch="x86_64",
        api_version=api_version,
        lan_ip="192.168.1.100",
        local_url="http://192.168.1.100",
        remote_url=None,
        license_type="Pro",
        license_state="valid",
        cpu_brand="Intel Core i7",
        cpu_cores=8,
        cpu_threads=16,
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-uuid-1234",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 80,
            CONF_API_KEY: "test-api-key",
            CONF_SSL: True,
        },
        title="tower",
    )


@pytest.fixture
def mock_server_info() -> ServerInfo:
    """Return a mock ServerInfo object."""
    return create_mock_server_info(uuid="test-uuid-1234")


def create_mock_unraid_client(
    mock_server_info: ServerInfo | None = None,
    mock_system_data: UnraidSystemData | None = None,
) -> MagicMock:
    """Create a mocked Unraid API client."""
    client = MagicMock()
    client.test_connection = AsyncMock(return_value=True)
    client.get_server_info = AsyncMock(
        return_value=mock_server_info or create_mock_server_info()
    )
    client.get_version = AsyncMock(return_value={"unraid": "7.2.0", "api": "4.29.2"})
    client.get_system_metrics = AsyncMock(
        return_value=(
            mock_system_data
            or UnraidSystemData(
                metrics=SystemMetrics(
                    cpu_percent=25.5,
                    cpu_temperature=45.0,
                    memory_percent=50.0,
                    memory_used=8_000_000_000,
                    memory_total=16_000_000_000,
                    uptime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
                ),
            )
        ).metrics
    )
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_system_data() -> UnraidSystemData:
    """Return mock system data for testing."""
    return UnraidSystemData(
        metrics=SystemMetrics(
            cpu_percent=25.5,
            cpu_temperature=45.0,
            memory_percent=50.0,
            memory_used=8_000_000_000,
            memory_total=16_000_000_000,
            uptime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
    )


@pytest.fixture
def mock_unraid_client(
    mock_server_info: ServerInfo,
    mock_system_data: UnraidSystemData,
) -> Generator[MagicMock]:
    """Return a mocked Unraid API client."""
    with (
        patch("homeassistant.components.unraid.UnraidClient") as mock_client_class,
        patch(
            "homeassistant.components.unraid.config_flow.UnraidClient",
            new=mock_client_class,
        ),
    ):
        client = create_mock_unraid_client(mock_server_info, mock_system_data)
        mock_client_class.return_value = client
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.unraid.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load for tests."""
    return [Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unraid_client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Unraid integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.unraid.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
