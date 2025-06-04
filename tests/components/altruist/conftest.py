"""AirGradient tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from altruistclient import AltruistDeviceModel
import pytest

from homeassistant.components.altruist.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.altruist.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "192.168.1.100", "id": "5366960e8b18"},
        unique_id="5366960e8b18",
    )


@pytest.fixture
def mock_altruist_device():
    """Return a mock AltruistDeviceModel."""
    device = Mock(spec=AltruistDeviceModel)
    device.id = "5366960e8b18"
    device.name = "Altruist Sensor"
    device.ip_address = "192.168.1.100"
    device.fw_version = "R_2025-03"
    return device


@pytest.fixture
def mock_altruist_client(mock_altruist_device):
    """Return a mock AltruistClient."""
    client = Mock()
    client.device = mock_altruist_device
    client.device_id = mock_altruist_device.id
    client.sensor_names = ["BME280_temperature", "BME280_humidity", "SDS_P1"]
    client.fetch_data = AsyncMock(
        return_value=[
            {"value_type": "BME280_temperature", "value": "25.5"},
            {"value_type": "BME280_humidity", "value": "60"},
            {"value_type": "SDS_P1", "value": "15"},
        ]
    )
    return client
