"""Common fixtures for the Droplet tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.droplet.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

MOCK_CODE = "11223"
MOCK_HOST = "192.168.1.2"
MOCK_PORT = 443
MOCK_DEVICE_ID = "Droplet-1234"
MOCK_MANUFACTURER = "Hydrific, part of LIXIL"
MOCK_SN = "1234"
MOCK_SW_VERSION = "v1.0.0"
MOCK_MODEL = "Droplet 1.0"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        unique_id=MOCK_DEVICE_ID,
    )


@pytest.fixture
def mock_droplet() -> Generator[AsyncMock]:
    """Mock a Droplet client."""
    with (
        patch(
            "homeassistant.components.droplet.coordinator.Droplet",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.get_signal_quality.return_value = "strong_signal"
        client.get_server_status.return_value = "connected"
        client.get_flow_rate.return_value = 0.1
        client.get_manufacturer.return_value = MOCK_MANUFACTURER
        client.get_model.return_value = MOCK_MODEL
        client.get_fw_version.return_value = MOCK_SW_VERSION
        client.get_sn.return_value = MOCK_SN
        yield client


@pytest.fixture
def mock_droplet_connection() -> Generator[AsyncMock]:
    """Mock a Droplet connection."""
    with (
        patch(
            "homeassistant.components.droplet.config_flow.DropletConnection",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        yield client


@pytest.fixture
def mock_droplet_discovery(request: pytest.FixtureRequest) -> Generator[AsyncMock]:
    """Mock a DropletDiscovery."""
    with (
        patch(
            "homeassistant.components.droplet.config_flow.DropletDiscovery",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        # Not all tests set this value
        try:
            client.host = request.param
        except AttributeError:
            client.host = MOCK_HOST
        client.port = MOCK_PORT
        client.try_connect.return_value = True
        client.get_device_id.return_value = MOCK_DEVICE_ID
        yield client


def mock_setup():
    """Mock setup function."""
    return True


@pytest.fixture
def mock_coordinator_setup():
    """Mock the droplet coordinator's setup."""
    with patch(
        "homeassistant.components.droplet.coordinator.DropletDataCoordinator.setup",
        new_callable=mock_setup,
    ) as coordinator_mock:
        yield coordinator_mock
