"""Airthings test configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from airthings import Airthings, AirthingsDevice
import pytest

from homeassistant.components.airthings.const import CONF_SECRET, DOMAIN
from homeassistant.const import CONF_ID

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ID: "client_id",
            CONF_SECRET: "secret",
        },
        unique_id="client_id",
    )


@pytest.fixture(params=["view_plus", "wave_plus", "wave_enhance"])
def airthings_fixture(
    request: pytest.FixtureRequest,
) -> str:
    """Return the fixture name for Airthings device types."""
    return request.param


@pytest.fixture
def mock_airthings_device(airthings_fixture: str) -> AirthingsDevice:
    """Mock an Airthings device."""
    return AirthingsDevice(
        **load_json_object_fixture(f"device_{airthings_fixture}.json", DOMAIN)
    )


@pytest.fixture
def mock_airthings_client(
    mock_airthings_device: AirthingsDevice, mock_airthings_token: AsyncMock
) -> Generator[Airthings]:
    """Mock an Airthings client."""
    with patch(
        "homeassistant.components.airthings.Airthings",
        autospec=True,
    ) as mock_airthings:
        client = mock_airthings.return_value
        client.update_devices.return_value = {
            mock_airthings_device.device_id: mock_airthings_device
        }
        yield client


@pytest.fixture
def mock_airthings_token() -> Generator[Airthings]:
    """Mock an Airthings client."""
    with (
        patch(
            "homeassistant.components.airthings.config_flow.airthings.get_token",
            return_value="test_token",
        ) as mock_get_token,
    ):
        yield mock_get_token


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airthings.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
