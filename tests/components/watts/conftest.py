"""Fixtures for the Watts integration tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest
from visionpluspython.models import create_device_from_data

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.watts.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

CLIENT_ID = "test_client_id"
CLIENT_SECRET = "test_client_secret"
TEST_DEVICE_ID = "test-device-id"
TEST_ACCESS_TOKEN = "test-access-token"
TEST_REFRESH_TOKEN = "test-refresh-token"
TEST_EXPIRES_AT = 9999999999


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Ensure the application credentials are registered for each test."""
    assert await async_setup_component(hass, "application_credentials", {})

    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET, name="Watts"),
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.watts.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_watts_client() -> Generator[AsyncMock]:
    """Mock a Watts Vision client."""
    with patch(
        "homeassistant.components.watts.WattsVisionClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value

        discover_data = json.loads(load_fixture("discover_devices.json", DOMAIN))
        device_report_data = json.loads(load_fixture("device_report.json", DOMAIN))
        device_detail_data = json.loads(load_fixture("device_detail.json", DOMAIN))

        discovered_devices = [
            create_device_from_data(device_data) for device_data in discover_data
        ]
        device_report = {
            device_id: create_device_from_data(device_data)
            for device_id, device_data in device_report_data.items()
        }
        device_detail = create_device_from_data(device_detail_data)

        client.discover_devices.return_value = discovered_devices
        client.get_devices_report.return_value = device_report
        client.get_device.return_value = device_detail
        client.set_thermostat_temperature = AsyncMock()
        client.set_thermostat_mode = AsyncMock()

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Watts Vision",
        data={
            "device_id": TEST_DEVICE_ID,
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_at": TEST_EXPIRES_AT,
            },
        },
        entry_id="01J0BC4QM2YBRP6H5G933CETI8",
        unique_id=TEST_DEVICE_ID,
    )
