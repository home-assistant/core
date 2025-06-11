"""Common fixtures for the Uptime Kuma tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, create_autospec, patch

import pytest
from pythonkuma import MonitorType, UptimeKumaMonitor
from pythonkuma.models import MonitorStatus

from homeassistant.components.uptime_kuma.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.uptime_kuma.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Uptime Kuma configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="uptime.example.org",
        data={
            CONF_URL: "https://uptime.example.org/",
            CONF_VERIFY_SSL: True,
            CONF_API_KEY: "apikey",
        },
        entry_id="123456789",
    )


@pytest.fixture
def mock_pyuptimekuma() -> Generator[AsyncMock]:
    """Mock pyuptimekuma client."""

    monitor_1 = create_autospec(
        spec=UptimeKumaMonitor,
        monitor_cert_days_remaining=90,
        monitor_cert_is_valid=1,
        monitor_hostname=None,
        monitor_name="Monitor 1",
        monitor_port=None,
        monitor_response_time=120,
        monitor_status=MonitorStatus.UP,
        monitor_type=MonitorType.HTTP,
        monitor_url="https://example.org",
    )
    monitor_2 = create_autospec(
        spec=UptimeKumaMonitor,
        monitor_cert_days_remaining=0,
        monitor_cert_is_valid=0,
        monitor_hostname=None,
        monitor_name="Monitor 2",
        monitor_port=None,
        monitor_response_time=28,
        monitor_status=MonitorStatus.UP,
        monitor_type=MonitorType.PORT,
        monitor_url=None,
    )
    monitor_3 = create_autospec(
        spec=UptimeKumaMonitor,
        monitor_cert_days_remaining=90,
        monitor_cert_is_valid=1,
        monitor_hostname=None,
        monitor_name="Monitor 3",
        monitor_port=None,
        monitor_response_time=120,
        monitor_status=MonitorStatus.DOWN,
        monitor_type=MonitorType.JSON_QUERY,
        monitor_url="https://down.example.org",
    )

    with (
        patch(
            "homeassistant.components.uptime_kuma.config_flow.UptimeKuma", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.uptime_kuma.coordinator.UptimeKuma",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        client.metrics.return_value = {
            "Monitor 1": monitor_1,
            "Monitor 2": monitor_2,
            "Monitor 3": monitor_3,
        }

        yield client
