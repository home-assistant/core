"""Common fixtures for the Aqvify tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pyaqvify import AqvifyAccount, AqvifyDeviceData, AqvifyDevices
import pytest

from homeassistant.components.aqvify.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aqvify.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        minor_version=1,
        domain=DOMAIN,
        title="Aqvify test",
        data={"api_key": "fake_api_key"},
        entry_id="aqvify_test",
        unique_id="test_account_id",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_aqvify_client(
    device_fixture: list[dict[str, Any]],
    device_data_fixture: dict[str, Any],
    account_fixture: dict[str, Any],
) -> Generator[MagicMock]:
    """Mock an Aqvify client."""

    with (
        patch(
            "homeassistant.components.aqvify.coordinator.AqvifyAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.aqvify.config_flow.AqvifyAPI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        client.async_get_account_id.return_value = AqvifyAccount(account_fixture)
        client.async_get_devices.return_value = AqvifyDevices(device_fixture)
        client.async_get_device_latest_data.return_value = AqvifyDeviceData(
            device_data_fixture
        )
        yield client


@pytest.fixture(scope="package")
def load_device_file() -> str:
    """Fixture for loading device file."""
    return "default_devices.json"


@pytest.fixture(scope="package")
def load_device_data_file() -> str:
    """Fixture for loading device data file."""
    return "default_device_data.json"


@pytest.fixture(scope="package")
def load_account_file() -> str:
    """Fixture for loading account file."""
    return "default_account.json"


@pytest.fixture
async def device_fixture(
    hass: HomeAssistant, load_device_file: str
) -> list[dict[str, Any]]:
    """Fixture for device."""
    return await async_load_json_array_fixture(hass, load_device_file, DOMAIN)


@pytest.fixture
async def device_data_fixture(
    hass: HomeAssistant, load_device_data_file: str
) -> dict[str, Any]:
    """Fixture for device data."""
    return await async_load_json_object_fixture(hass, load_device_data_file, DOMAIN)


@pytest.fixture
async def account_fixture(
    hass: HomeAssistant, load_account_file: str
) -> dict[str, Any]:
    """Fixture for account data."""
    return await async_load_json_object_fixture(hass, load_account_file, DOMAIN)
