"""Test configuration and mocks for the SmartThings component."""

from collections.abc import Generator
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from pysmartthings import (
    DeviceHealth,
    LocationResponse,
    RoomResponse,
    SceneResponse,
    Subscription,
)
from pysmartthings.models import HealthStatus, InstalledApp
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_fixture

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.smartthings import CONF_INSTALLED_APP_ID, OLD_DATA
from homeassistant.components.smartthings.const import (
    CONF_APP_ID,
    CONF_LOCATION_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    SCOPES,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import DEVICE_FIXTURES, get_device_response, get_device_status, get_fixture_name


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smartthings.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("CLIENT_ID", "CLIENT_SECRET"),
        DOMAIN,
    )


@pytest.fixture
def mock_smartthings() -> Generator[AsyncMock]:
    """Mock a SmartThings client."""
    with (
        patch(
            "homeassistant.components.smartthings.SmartThings",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.smartthings.config_flow.SmartThings",
            new=mock_client,
        ),
        # pysmartthings doesn't have create_app/delete_app yet, so autospec
        # doesn't know about them -- create=True adds them as plain AsyncMocks
        # until the real methods exist and this can go through autospec too.
        patch.object(
            mock_client.return_value,
            "create_app",
            create=True,
            new_callable=AsyncMock,
        ),
        patch.object(
            mock_client.return_value,
            "delete_app",
            create=True,
            new_callable=AsyncMock,
        ),
    ):
        client = mock_client.return_value
        client.get_scenes.return_value = SceneResponse.from_json(
            load_fixture("scenes.json", DOMAIN)
        ).items
        client.get_locations.return_value = LocationResponse.from_json(
            load_fixture("locations.json", DOMAIN)
        ).items
        client.get_rooms.return_value = RoomResponse.from_json(
            load_fixture("rooms.json", DOMAIN)
        ).items
        client.create_subscription.return_value = Subscription.from_json(
            load_fixture("subscription.json", DOMAIN)
        )
        client.get_device_health.return_value = DeviceHealth.from_json(
            load_fixture("device_health.json", DOMAIN)
        )
        client.get_installed_app.return_value = InstalledApp.from_json(
            load_fixture("installed_app.json", DOMAIN)
        )
        # Stand-in for pysmartthings' not-yet-existing AppRegistration model.
        client.create_app.return_value = SimpleNamespace(
            app_id="mock-app-id",
            client_id="mock-client-id",
            client_secret="mock-client-secret",
        )
        client.delete_app.return_value = None
        yield client


@pytest.fixture
def device_fixture() -> str | None:
    """Return every device."""
    return None


@pytest.fixture
def devices(mock_smartthings: AsyncMock, device_fixture: str | None) -> AsyncMock:
    """Return a specific device."""
    if device_fixture is not None:
        mock_smartthings.get_devices.return_value = get_device_response(
            device_fixture
        ).items
        mock_smartthings.get_device_status.return_value = get_device_status(
            device_fixture
        ).components
    else:
        devices = []
        for device_name in DEVICE_FIXTURES:
            devices.extend(get_device_response(device_name).items)
        mock_smartthings.get_devices.return_value = devices

        async def _get_device_status(device_id: str):
            return get_device_status(get_fixture_name(device_id)).components

        mock_smartthings.get_device_status.side_effect = _get_device_status

    return mock_smartthings


@pytest.fixture
def unavailable_device(devices: AsyncMock) -> AsyncMock:
    """Mock an unavailable device."""
    devices.get_device_health.return_value.state = HealthStatus.OFFLINE
    return devices


@pytest.fixture
def mock_config_entry(expires_at: int) -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="My home",
        unique_id="397678e5-9995-4a39-9d9f-ae6ba310236c",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(SCOPES),
                "access_tier": 0,
                "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
            },
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123",
        },
        version=3,
        minor_version=3,
    )


@pytest.fixture
def mock_config_entry_with_app_id(expires_at: int) -> MockConfigEntry:
    """Mock a config entry provisioned via the PAT flow, owning an app id."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="My home",
        unique_id="397678e5-9995-4a39-9d9f-ae6ba310236c",
        data={
            "auth_implementation": f"{DOMAIN}_existing-app-id",
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(SCOPES),
                "access_tier": 0,
                "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
            },
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123",
            # Deliberately distinct from mock_smartthings' default
            # create_app.return_value.app_id ("mock-app-id"), so tests using
            # both a live entry and a freshly-created app can tell them apart.
            CONF_APP_ID: "existing-app-id",
        },
        version=3,
        minor_version=3,
    )


@pytest.fixture
def old_data() -> dict[str, Any]:
    """Return old data for config entry."""
    return {
        OLD_DATA: {
            CONF_ACCESS_TOKEN: "mock-access-token",
            CONF_REFRESH_TOKEN: "mock-refresh-token",
            CONF_CLIENT_ID: "CLIENT_ID",
            CONF_CLIENT_SECRET: "CLIENT_SECRET",
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123aa123-2be1-4e40-b257-e4ef59083324",
        }
    }


@pytest.fixture
def mock_migrated_config_entry(
    expires_at: int, old_data: dict[str, Any]
) -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="My home",
        unique_id="397678e5-9995-4a39-9d9f-ae6ba310236c",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(SCOPES),
                "access_tier": 0,
                "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
            },
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123",
            **old_data,
        },
        version=3,
        minor_version=2,
    )


@pytest.fixture
def mock_old_config_entry() -> MockConfigEntry:
    """Mock the old config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="My home",
        unique_id="appid123-2be1-4e40-b257-e4ef59083324_397678e5-9995-4a39-9d9f-ae6ba310236c",
        data={
            CONF_ACCESS_TOKEN: "mock-access-token",
            CONF_REFRESH_TOKEN: "mock-refresh-token",
            CONF_CLIENT_ID: "CLIENT_ID",
            CONF_CLIENT_SECRET: "CLIENT_SECRET",
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123aa123-2be1-4e40-b257-e4ef59083324",
        },
        version=2,
    )
