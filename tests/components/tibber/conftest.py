"""Test helpers for Tibber."""

from collections.abc import AsyncGenerator
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import tibber

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import AUTH_IMPLEMENTATION, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


def create_tibber_device(
    device_id: str = "device-id",
    external_id: str = "external-id",
    name: str = "Test Device",
    brand: str = "Tibber",
    model: str = "Gen1",
    value: float | None = 72.0,
    home_id: str = "home-id",
) -> tibber.data_api.TibberDevice:
    """Create a fake Tibber Data API device."""
    device_data = {
        "id": device_id,
        "externalId": external_id,
        "info": {
            "name": name,
            "brand": brand,
            "model": model,
        },
        "capabilities": [
            {
                "id": "storage.stateOfCharge",
                "value": value,
                "description": "State of charge",
                "unit": "%",
            },
            {
                "id": "unknown.sensor.id",
                "value": None,
                "description": "Unknown",
                "unit": "",
            },
        ],
    }
    return tibber.data_api.TibberDevice(device_data, home_id=home_id)


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Tibber config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: "token",
            AUTH_IMPLEMENTATION: DOMAIN,
            "token": {
                "access_token": "test-token",
                "refresh_token": "refresh-token",
                "token_type": "Bearer",
                "expires_at": time.time() + 3600,
            },
        },
        unique_id="tibber",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def tibber_mock() -> AsyncGenerator[MagicMock]:
    """Patch the Tibber libraries used by the integration."""
    unique_user_id = "unique_user_id"
    title = "title"

    with patch(
        "tibber.Tibber",
        autospec=True,
    ) as mock_tibber:
        tibber_mock = mock_tibber.return_value
        tibber_mock.update_info = AsyncMock(return_value=True)
        tibber_mock.user_id = unique_user_id
        tibber_mock.name = title
        tibber_mock.send_notification = AsyncMock()
        tibber_mock.rt_disconnect = AsyncMock()
        tibber_mock.get_homes = MagicMock(return_value=[])
        tibber_mock.set_access_token = MagicMock()

        data_api_mock = MagicMock()
        data_api_mock.get_all_devices = AsyncMock(return_value={})
        data_api_mock.update_devices = AsyncMock(return_value={})
        data_api_mock.get_userinfo = AsyncMock()
        tibber_mock.data_api = data_api_mock

        yield tibber_mock


@pytest.fixture
def data_api_client_mock(tibber_mock: MagicMock) -> MagicMock:
    """Return the patched Tibber Data API client mock."""
    return tibber_mock.data_api


@pytest.fixture
async def mock_tibber_setup(
    recorder_mock: Recorder,
    config_entry: MockConfigEntry,
    hass: HomeAssistant,
    tibber_mock: MagicMock,
    setup_credentials: None,
) -> MagicMock:
    """Mock tibber entry setup."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return tibber_mock


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up application credentials for the OAuth flow."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("test-client-id", "test-client-secret"),
        DOMAIN,
    )
