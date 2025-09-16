"""Altruist tests configuration."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, Mock, patch

from altruistclient import AltruistDeviceModel, AltruistError
import pytest

from homeassistant.components.altruist.const import CONF_HOST, DOMAIN

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.altruist.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="5366960e8b18",
        title="5366960e8b18",
    )


@pytest.fixture
def mock_altruist_device() -> Mock:
    """Return a mock AltruistDeviceModel."""
    device = Mock(spec=AltruistDeviceModel)
    device.id = "5366960e8b18"
    device.name = "Altruist Sensor"
    device.ip_address = "192.168.1.100"
    device.fw_version = "R_2025-03"
    return device


@pytest.fixture
def mock_altruist_client(mock_altruist_device: Mock) -> Generator[AsyncMock]:
    """Return a mock AltruistClient."""
    with (
        patch(
            "homeassistant.components.altruist.coordinator.AltruistClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.altruist.config_flow.AltruistClient",
            new=mock_client_class,
        ),
    ):
        mock_instance = AsyncMock()
        mock_instance.device = mock_altruist_device
        mock_instance.device_id = mock_altruist_device.id
        mock_instance.sensor_names = json.loads(
            load_fixture("sensor_names.json", DOMAIN)
        )
        mock_instance.fetch_data.return_value = json.loads(
            load_fixture("real_data.json", DOMAIN)
        )

        mock_client_class.from_ip_address = AsyncMock(return_value=mock_instance)

        yield mock_instance


@pytest.fixture
def mock_altruist_client_fails_once(mock_altruist_client: AsyncMock) -> Generator[None]:
    """Patch AltruistClient to fail once and then succeed."""
    with patch(
        "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
        side_effect=[AltruistError("Connection failed"), mock_altruist_client],
    ):
        yield
