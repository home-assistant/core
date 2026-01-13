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
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


def create_tibber_device(
    device_id: str = "device-id",
    external_id: str = "external-id",
    name: str = "Test Device",
    brand: str = "Tibber",
    model: str = "Gen1",
    home_id: str = "home-id",
    state_of_charge: float | None = None,
    connector_status: str | None = None,
    charging_status: str | None = None,
    device_status: str | None = None,
) -> tibber.data_api.TibberDevice:
    """Create a fake Tibber Data API device.

    Args:
        device_id: Device ID.
        external_id: External device ID.
        name: Device name.
        brand: Device brand.
        model: Device model.
        home_id: Home ID.
        state_of_charge: Battery state of charge (for regular sensors).
        connector_status: Connector status (for binary sensors).
        charging_status: Charging status (for binary sensors).
        device_status: Device on/off status (for binary sensors).
    """
    capabilities = []

    # Add regular sensor capabilities
    if state_of_charge is not None:
        capabilities.append(
            {
                "id": "storage.stateOfCharge",
                "value": state_of_charge,
                "description": "State of charge",
                "unit": "%",
            }
        )
        capabilities.append(
            {
                "id": "unknown.sensor.id",
                "value": None,
                "description": "Unknown",
                "unit": "",
            }
        )

    # Add binary sensor capabilities
    if connector_status is not None:
        capabilities.append(
            {
                "id": "connector.status",
                "value": connector_status,
                "description": "Connector status",
                "unit": "",
            }
        )

    if charging_status is not None:
        capabilities.append(
            {
                "id": "charging.status",
                "value": charging_status,
                "description": "Charging status",
                "unit": "",
            }
        )

    if device_status is not None:
        capabilities.append(
            {
                "id": "onOff",
                "value": device_status,
                "description": "Device status",
                "unit": "",
            }
        )

    device_data = {
        "id": device_id,
        "externalId": external_id,
        "info": {
            "name": name,
            "brand": brand,
            "model": model,
        },
        "capabilities": capabilities,
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
def _tibber_patches() -> AsyncGenerator[tuple[MagicMock, MagicMock]]:
    """Patch the Tibber libraries used by the integration."""
    unique_user_id = "unique_user_id"
    title = "title"

    with (
        patch(
            "tibber.Tibber",
            autospec=True,
        ) as mock_tibber,
        patch(
            "tibber.data_api.TibberDataAPI",
            autospec=True,
        ) as mock_data_api_client,
    ):
        tibber_mock = mock_tibber.return_value
        tibber_mock.update_info = AsyncMock(return_value=True)
        tibber_mock.user_id = unique_user_id
        tibber_mock.name = title
        tibber_mock.send_notification = AsyncMock()
        tibber_mock.rt_disconnect = AsyncMock()
        tibber_mock.get_homes = MagicMock(return_value=[])

        data_api_client_mock = mock_data_api_client.return_value
        data_api_client_mock.get_all_devices = AsyncMock(return_value={})
        data_api_client_mock.update_devices = AsyncMock(return_value={})

        yield tibber_mock, data_api_client_mock


@pytest.fixture
def tibber_mock(_tibber_patches: tuple[MagicMock, MagicMock]) -> MagicMock:
    """Return the patched Tibber connection mock."""
    return _tibber_patches[0]


@pytest.fixture
def data_api_client_mock(_tibber_patches: tuple[MagicMock, MagicMock]) -> MagicMock:
    """Return the patched Tibber Data API client mock."""
    return _tibber_patches[1]


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


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR, Platform.NOTIFY, Platform.SENSOR]


@pytest.fixture(autouse=True)
async def mock_patch_platforms(platforms: list[Platform]) -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        yield
