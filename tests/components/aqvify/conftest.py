"""Common fixtures for the Aqvify tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
        unique_id="aqvify_unique_id",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_aqvify_client(
    device_fixture,
    device_data_fixture,
) -> Generator[MagicMock]:
    """Mock an Aqify client."""

    with (
        patch(
            "homeassistant.components.aqvify.AqvifyAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.aqvify.coordinator.AqvifyAPI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        client.async_get_devices.return_value = device_fixture
        client.async_get_device_latest_data.return_value = device_data_fixture
        client.async_get_account_id.return_value = {"accountId": "Account"}
        yield client


@pytest.fixture(scope="package")
def load_device_file() -> str:
    """Fixture for loading device file."""
    return "default_devices.json"


@pytest.fixture(scope="package")
def load_device_data_file() -> str:
    """Fixture for loading device data file."""
    return "default_device_data.json"


@pytest.fixture
async def device_fixture(hass: HomeAssistant, load_device_file: str) -> dict[str, Any]:
    """Fixture for device."""
    return await async_load_json_array_fixture(hass, load_device_file, DOMAIN)
    # return load_json_value_fixture(load_device_file, DOMAIN)


@pytest.fixture
async def device_data_fixture(
    hass: HomeAssistant, load_device_data_file: str
) -> dict[str, Any]:
    """Fixture for device data."""
    return await async_load_json_object_fixture(hass, load_device_data_file, DOMAIN)
