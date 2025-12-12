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
from homeassistant.components.tibber import TibberRuntimeData
from homeassistant.components.tibber.const import AUTH_IMPLEMENTATION, DOMAIN
from homeassistant.components.tibber.coordinator import TibberDataAPICoordinator
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
    tibber_mock.get_homes = MagicMock(return_value=[])

    session_mock = MagicMock()
    session_mock.async_ensure_token_valid = AsyncMock()
    session_mock.token = {CONF_ACCESS_TOKEN: "test-token"}

    implementation_mock = MagicMock()

    data_api_client_mock = MagicMock()
    data_api_client_mock.get_all_devices = AsyncMock(return_value={})
    data_api_client_mock.update_devices = AsyncMock(return_value={})

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
        patch(
            "homeassistant.components.tibber.coordinator.TibberDataAPICoordinator._async_get_client",
            return_value=data_api_client_mock,
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


@pytest.fixture
def data_api_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Data API Tibber config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "token"},
        unique_id="data-api",
    )
    entry.add_to_hass(hass)
    return entry


def create_mock_runtime(
    async_get_client: AsyncMock | None = None,
    tibber_connection: MagicMock | None = None,
    coordinator_data: dict | None = None,
) -> TibberRuntimeData:
    """Create a mock TibberRuntimeData.

    Args:
        async_get_client: Optional async mock for getting the Data API client.
        tibber_connection: Optional mock for the GraphQL connection.
        coordinator_data: Optional data dict for the coordinator.

    """
    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = {CONF_ACCESS_TOKEN: "test-token"}

    coordinator = MagicMock(spec=TibberDataAPICoordinator)
    coordinator.data = coordinator_data if coordinator_data is not None else {}
    coordinator.sensors_by_device = {}

    runtime = MagicMock(spec=TibberRuntimeData)
    runtime.session = session
    runtime.tibber_connection = tibber_connection or MagicMock()
    runtime.tibber_connection.get_homes = MagicMock(return_value=[])
    runtime.data_api_coordinator = coordinator
    runtime.async_get_client = async_get_client or AsyncMock()

    return runtime
