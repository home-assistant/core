"""Airthings test configuration."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

from airthings import Airthings, AirthingsDevice
import pytest

from homeassistant.components.airthings.const import DOMAIN

from . import TEST_DATA

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
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
    mock_airthings_device: AirthingsDevice,
) -> Generator[Airthings]:
    """Mock an Airthings client."""
    mock_airthings = AsyncMock()

    with (
        patch("airthings.get_token", return_value="test_token"),
    ):
        mock_airthings.update_devices.return_value = {
            mock_airthings_device.device_id: mock_airthings_device
        }
        yield mock_airthings
