"""Fixtures for the Netio integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from Netio import Netio
import pytest

from homeassistant.components.netio.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.netio.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_netio() -> Generator[MagicMock]:
    """Mock a Netio JSON API client."""
    with patch(
        "homeassistant.components.netio.coordinator.Netio", autospec=True
    ) as netio_mock:
        device = netio_mock.return_value
        device.SerialNumber = "24A42C39F87E"
        device.DeviceName = "PowerCable"
        device.get_info.return_value = {
            "Agent": {
                "DeviceName": "PowerCable",
                "MAC": "24:A4:2C:39:F8:7E",
                "Model": "101x",
                "NumOutputs": 2,
                "SerialNumber": "24A42C39F87E",
                "Version": "3.1.4",
            }
        }
        device.get_outputs.return_value = [
            Netio.OUTPUT(
                ID=1,
                Name="Output 1",
                State=1,
                Action=Netio.ACTION.ON,
                Delay=5000,
                Current=61,
                PowerFactor=0.61,
                Load=14,
                Energy=6673,
            ),
            Netio.OUTPUT(
                ID=2,
                Name="Fridge",
                State=0,
                Action=Netio.ACTION.OFF,
                Delay=5000,
                Current=0,
                PowerFactor=0.0,
                Load=0,
                Energy=142,
            ),
        ]
        yield netio_mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Netio config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="PowerCable",
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: 80,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "netio-password",
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
        unique_id="24A42C39F87E",
    )
