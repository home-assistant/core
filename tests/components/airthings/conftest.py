"""Airthings test configuration."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

from airthings import Airthings, AirthingsDevice
import pytest

from homeassistant.components.airthings.const import CONF_SECRET, DOMAIN
from homeassistant.const import CONF_ID

from tests.common import MockConfigEntry, load_fixture


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
def mock_airthings_device(
    request: pytest.FixtureRequest,
) -> AirthingsDevice:
    """Mock an Airthings device."""

    device_as_json_string = load_fixture(f"device_{request.param}.json", DOMAIN)
    device_as_json = json.loads(device_as_json_string)

    return AirthingsDevice(**device_as_json)


@pytest.fixture
def mock_airthings_client(
    mock_airthings_device: AirthingsDevice, mock_airthings_token: AsyncMock
) -> Generator[Airthings]:
    """Mock an Airthings client."""
    with (
        patch(
            "homeassistant.components.airthings.Airthings",
            autospec=True,
        ) as mock_airthings,
        patch(
            "homeassistant.components.airthings.config_flow.airthings.get_token",
            return_value="test_token",
        ),
    ):
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
