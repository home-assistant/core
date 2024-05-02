"""Test helpers for myuplink."""

from collections.abc import AsyncGenerator, Generator
import time
from typing import Any
from unittest.mock import MagicMock, patch

from myuplink import Device, DevicePoint, System
import orjson
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.myuplink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.json import json_loads

from .const import CLIENT_ID, CLIENT_SECRET

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, expires_at: float) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="myUplink test",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "Fake_token",
                "scope": "WRITESYSTEM READSYSTEM offline_access",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
        entry_id="myuplink_test",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            CLIENT_ID,
            CLIENT_SECRET,
        ),
        DOMAIN,
    )


# Fixture group for device API endpoint.


@pytest.fixture(scope="package")
def load_device_file() -> str:
    """Fixture for loading device file."""
    return load_fixture("device.json", DOMAIN)


@pytest.fixture
def device_fixture(load_device_file: str) -> Device:
    """Fixture for device."""
    return Device(json_loads(load_device_file))


# Fixture group for systems API endpoint.


@pytest.fixture
def load_systems_jv_file(load_systems_file: str) -> dict[str, Any]:
    """Load fixture file for systems endpoint."""
    return json_loads(load_systems_file)


@pytest.fixture(scope="package")
def load_systems_file() -> str:
    """Load fixture file for systems."""
    return load_fixture("systems-2dev.json", DOMAIN)


@pytest.fixture
def system_fixture(load_systems_file: str) -> list[System]:
    """Fixture for systems."""
    data = json_loads(load_systems_file)
    return [System(system_data) for system_data in data["systems"]]


# Fixture group for device points API endpoint.


@pytest.fixture
def load_device_points_file() -> str:
    """Load fixture file for device-points endpoint."""
    return "device_points_nibe_f730.json"


@pytest.fixture
def load_device_points_jv_file(load_device_points_file) -> str:
    """Load fixture file for device_points."""
    return load_fixture(load_device_points_file, DOMAIN)


@pytest.fixture
def device_points_fixture(load_device_points_jv_file: str) -> list[DevicePoint]:
    """Fixture for device_points."""
    data = orjson.loads(load_device_points_jv_file)
    return [DevicePoint(point_data) for point_data in data]


@pytest.fixture
def mock_myuplink_client(
    load_device_file,
    device_fixture,
    load_device_points_jv_file,
    device_points_fixture,
    system_fixture,
    load_systems_jv_file,
) -> Generator[MagicMock, None, None]:
    """Mock a myuplink client."""

    with patch(
        "homeassistant.components.myuplink.MyUplinkAPI",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value

        client.async_get_systems.return_value = system_fixture
        client.async_get_systems_json.return_value = load_systems_jv_file

        client.async_get_device.return_value = device_fixture
        client.async_get_device_json.return_value = load_device_file

        client.async_get_device_points.return_value = device_points_fixture
        client.async_get_device_points_json.return_value = load_device_points_jv_file

        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_myuplink_client: MagicMock,
) -> MockConfigEntry:
    """Set up the myuplink integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms."""
    return []


@pytest.fixture
async def setup_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms,
) -> AsyncGenerator[None, None]:
    """Set up one or all platforms."""

    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield
