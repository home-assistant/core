"""Common fixtures for the AirPatrol tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from airpatrol.api import AirPatrolAPI
import pytest

from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEFAULT_UNIT_ID = "test_unit_001"


@pytest.fixture(name="get_client")
def mock_airpatrol_client(get_data) -> Generator[AsyncMock]:
    """Mock an AirPatrol client and config."""
    with (
        patch(
            "homeassistant.components.airpatrol.coordinator.AirPatrolAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.airpatrol.config_flow.AirPatrolAPI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_unique_id.return_value = "test_user_id"
        client.get_access_token.return_value = "test_access_token"
        client.get_data.return_value = get_data
        client.set_unit_climate_data.return_value = AsyncMock()
        mock_client.authenticate.return_value = client

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test_password",
            CONF_ACCESS_TOKEN: "test_access_token",
        },
        unique_id="test_user_id",
        title="test@example.com",
    )


@pytest.fixture
async def load_integration(
    hass: HomeAssistant,
    get_client: AirPatrolAPI,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Load the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
def get_data(climate_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return data."""
    return [
        {
            "unit_id": DEFAULT_UNIT_ID,
            "name": "living room",
            "manufacturer": "AirPatrol",
            "model": "apw",
            "hwid": "hw01",
            "climate": climate_data,
        }
    ]


@pytest.fixture
def climate_data() -> dict[str, Any]:
    """Return data."""
    return {
        "ParametersData": {
            "PumpPower": "on",
            "PumpTemp": "22.000",
            "PumpMode": "cool",
            "FanSpeed": "max",
            "Swing": "off",
        },
        "RoomTemp": "22.5",
        "RoomHumidity": "45",
    }
