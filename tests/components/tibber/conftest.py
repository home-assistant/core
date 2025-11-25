"""Test helpers for Tibber."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
import tibber

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import DOMAIN
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
            "auth_implementation": DOMAIN,
        },
        unique_id="tibber",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
async def mock_tibber_setup(
    recorder_mock: Recorder, config_entry: MockConfigEntry, hass: HomeAssistant
) -> AsyncGenerator[MagicMock]:
    """Mock tibber entry setup."""
    unique_user_id = "unique_user_id"
    title = "title"

    tibber_mock = MagicMock()
    tibber_mock.update_info = AsyncMock(return_value=True)
    tibber_mock.user_id = PropertyMock(return_value=unique_user_id)
    tibber_mock.name = PropertyMock(return_value=title)
    tibber_mock.send_notification = AsyncMock()
    tibber_mock.rt_disconnect = AsyncMock()

    session_mock = MagicMock()
    session_mock.async_ensure_token_valid = AsyncMock()
    session_mock.token = {CONF_ACCESS_TOKEN: "test-token"}

    implementation_mock = MagicMock()

    with (
        patch("tibber.Tibber", return_value=tibber_mock),
        patch(
            "homeassistant.components.tibber.async_get_config_entry_implementation",
            return_value=implementation_mock,
        ),
        patch(
            "homeassistant.components.tibber.OAuth2Session",
            return_value=session_mock,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield tibber_mock


@pytest.fixture
async def setup_credentials(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Set up application credentials for the OAuth flow."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("test-client-id", "test-client-secret"),
        DOMAIN,
    )
