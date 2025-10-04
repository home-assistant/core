"""Common fixtures for the LibreHardwareMonitor tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from librehardwaremonitor_api.parser import LibreHardwareMonitorParser
import pytest

from homeassistant.components.libre_hardware_monitor.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry, load_json_object_fixture

VALID_CONFIG = {CONF_HOST: "192.168.0.20", CONF_PORT: 8085}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.libre_hardware_monitor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="192.168.0.20:8085",
        data=VALID_CONFIG,
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_lhm_client() -> Generator[AsyncMock]:
    """Mock a LibreHardwareMonitor client."""
    with (
        patch(
            "homeassistant.components.libre_hardware_monitor.config_flow.LibreHardwareMonitorClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.libre_hardware_monitor.coordinator.LibreHardwareMonitorClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        test_data_json = load_json_object_fixture(
            "libre_hardware_monitor.json", "libre_hardware_monitor"
        )
        test_data = LibreHardwareMonitorParser().parse_data(test_data_json)
        client.get_data.return_value = test_data

        yield client
