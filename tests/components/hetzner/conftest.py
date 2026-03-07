"""Test fixtures for the Hetzner Cloud integration."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from hcloud.load_balancer_types.domain import LoadBalancerType
from hcloud.load_balancers.domain import (
    LoadBalancerTarget,
    LoadBalancerTargetHealthStatus,
    LoadBalancerTargetIP,
)
from hcloud.servers.domain import Server
import pytest

from homeassistant.components.hetzner.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Hetzner Cloud",
        domain=DOMAIN,
        data={CONF_API_TOKEN: "test-api-token-12345"},
        unique_id="8c8ce69e7409",
    )


def _build_mock_load_balancers() -> list[MagicMock]:
    """Build mock load balancer objects."""
    lb_type = LoadBalancerType(
        id=1,
        name="lb11",
        description="LB11",
        max_connections=10000,
        max_services=5,
        max_targets=25,
        max_assigned_certificates=10,
    )

    server = Server(id=101, name="web-1")
    target_server = LoadBalancerTarget(
        type="server",
        server=server,
        health_status=[
            LoadBalancerTargetHealthStatus(listen_port=80, status="healthy"),
            LoadBalancerTargetHealthStatus(listen_port=443, status="healthy"),
        ],
    )

    target_ip = LoadBalancerTarget(
        type="ip",
        ip=LoadBalancerTargetIP(ip="10.0.0.1"),
        health_status=[
            LoadBalancerTargetHealthStatus(listen_port=80, status="unhealthy"),
        ],
    )

    lb_mock = MagicMock()
    lb_mock.data_model.id = 42
    lb_mock.data_model.name = "my-load-balancer"
    lb_mock.data_model.load_balancer_type = lb_type
    lb_mock.data_model.targets = [target_server, target_ip]

    return [lb_mock]


@pytest.fixture
def mock_hcloud() -> Generator[MagicMock]:
    """Return a mocked hcloud Client."""
    with patch(
        "homeassistant.components.hetzner.Client",
    ) as client_mock:
        client = client_mock.return_value
        client.load_balancers.get_all.return_value = _build_mock_load_balancers()
        yield client


@pytest.fixture
def mock_hcloud_config_flow() -> Generator[MagicMock]:
    """Return a mocked hcloud Client for config flow."""
    with patch(
        "homeassistant.components.hetzner.config_flow.Client",
    ) as client_mock:
        client = client_mock.return_value
        client.load_balancers.get_all.return_value = _build_mock_load_balancers()
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcloud: MagicMock,
) -> MockConfigEntry:
    """Set up the Hetzner Cloud integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
