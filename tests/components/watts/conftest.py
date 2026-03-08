"""Fixtures for the Watts integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from visionpluspython.models import Device, create_device_from_data

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.watts.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

CLIENT_ID = "test_client_id"
CLIENT_SECRET = "test_client_secret"
TEST_USER_ID = "test-user-id"
TEST_ACCESS_TOKEN = "test-access-token"
TEST_REFRESH_TOKEN = "test-refresh-token"
TEST_ID_TOKEN = "test-id-token"
TEST_PROFILE_INFO = "test-profile-info"
TEST_EXPIRES_AT = 9999999999


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Ensure the application credentials are registered for each test."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})

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

        discover_data = load_json_array_fixture("discover_devices.json", DOMAIN)
        device_report_data = load_json_object_fixture("device_report.json", DOMAIN)
        device_detail_data = load_json_object_fixture("device_detail.json", DOMAIN)
        switch_detail_data = load_json_object_fixture("switch_detail.json", DOMAIN)

        discovered_devices = [
            create_device_from_data(device_data)  # type: ignore[arg-type]
            for device_data in discover_data
        ]
        device_report = {
            device_id: create_device_from_data(device_data)  # type: ignore[arg-type]
            for device_id, device_data in device_report_data.items()
        }
        device_detail = create_device_from_data(device_detail_data)  # type: ignore[arg-type]
        switch_detail = create_device_from_data(switch_detail_data)  # type: ignore[arg-type]

        device_details = {
            device_detail_data["deviceId"]: device_detail,
            switch_detail_data["deviceId"]: switch_detail,
        }

        async def get_device_side_effect(
            device_id: str, refresh: bool = False
        ) -> Device:
            """Return the appropriate device based on device_id."""
            return device_details.get(device_id, device_detail)

        client.discover_devices.return_value = discovered_devices
        client.get_devices_report.return_value = device_report
        client.get_device.side_effect = get_device_side_effect

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Watts Vision",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "id_token": TEST_ID_TOKEN,
                "profile_info": TEST_PROFILE_INFO,
                "expires_at": TEST_EXPIRES_AT,
            },
        },
        entry_id="01J0BC4QM2YBRP6H5G933CETI8",
        unique_id=TEST_USER_ID,
    )


@pytest.fixture(name="skip_cloud", autouse=True)
def skip_cloud_fixture():
    """Skip setting up cloud.

    Cloud already has its own tests for account link.

    We do not need to test it here as we only need to test our
    usage of the oauth2 helpers.
    """
    with patch("homeassistant.components.cloud.async_setup", return_value=True):
        yield
