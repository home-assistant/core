"""Common fixtures for the LibreHardwareMonitor tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.librehardwaremonitor.const import DOMAIN

from tests.common import load_json_object_fixture


@pytest.fixture
def mock_lhm_client() -> Generator[AsyncMock]:
    """Mock a LibreHardwareMonitor client."""
    data_json = load_json_object_fixture("librehardwaremonitor.json", DOMAIN)

    with (
        patch(
            "homeassistant.components.librehardwaremonitor.config_flow.LibreHardwareMonitorClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.librehardwaremonitor.coordinator.LibreHardwareMonitorClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_data_json.return_value = data_json
        client.get_hardware_device_names.return_value = [
            "MSI MAG B650M MORTAR WIFI (MS-7D76)",
            "AMD Ryzen 7 7800X3D",
            "Generic Memory",
            "Samsung SSD 970 EVO 1TB",
        ]

        yield client
