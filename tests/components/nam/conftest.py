"""Common fixtures for the Nettigo Air Monitor tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from nettigo_air_monitor import NAMSensors
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.nam.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

NAM_SENSORS = NAMSensors(**load_json_object_fixture("nam_sensors.json", DOMAIN))


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nam.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="10.10.2.3",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={CONF_HOST: "10.10.2.3"},
    )


@pytest.fixture
def mock_config_entry_with_auth() -> MockConfigEntry:
    """Mock a config entry with credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="10.10.2.3",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={
            CONF_HOST: "10.10.2.3",
            CONF_USERNAME: "fake_username",
            CONF_PASSWORD: "fake_password",
        },
    )


@pytest.fixture
def mock_nam() -> Generator[MagicMock]:
    """Mock the NettigoAirMonitor class."""
    with (
        patch(
            "homeassistant.components.nam.NettigoAirMonitor", autospec=True
        ) as mock_class,
        patch(
            "homeassistant.components.nam.config_flow.NettigoAirMonitor", new=mock_class
        ),
    ):
        yield mock_class


@pytest.fixture
def mock_nam_client(mock_nam: MagicMock) -> MagicMock:
    """Mock a NettigoAirMonitor client instance."""
    client = mock_nam.return_value
    mock_nam.create.return_value = client
    client.async_update.return_value = NAM_SENSORS
    client.host = "10.10.2.3"
    client.mac = "aa:bb:cc:dd:ee:ff"
    client.software_version = "NAMF-2020-36"

    return client
