"""Common fixtures for the AirPatrol tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from airpatrol.api import AirPatrolAPI
import pytest

from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.conftest import MockConfigEntry


@pytest.fixture
def _mock_airpatrol_client_config_flow(get_data) -> Generator[AsyncMock, AsyncMock]:
    """Mock an AirPatrol client and config."""
    with (
        patch(
            "homeassistant.components.airpatrol.coordinator.AirPatrolAPI",
            autospec=True,
        ) as mock_coordinator_client,
        patch(
            "homeassistant.components.airpatrol.config_flow.AirPatrolAPI",
            autospec=True,
        ) as mock_config_flow_client,
    ):
        client_instance = MagicMock(spec=AirPatrolAPI)
        client_instance.get_unique_id.return_value = "test_user_id"
        client_instance.get_access_token.return_value = "test_access_token"
        client_instance.get_data.return_value = get_data()
        client_instance.set_unit_climate_data.return_value = AsyncMock()
        mock_coordinator_client.return_value = client_instance
        mock_coordinator_client.authenticate = AsyncMock(return_value=client_instance)
        mock_config_flow_client.authenticate = AsyncMock(return_value=client_instance)
        yield client_instance, mock_config_flow_client, mock_coordinator_client


@pytest.fixture
def mock_airpatrol_client_coordinator(_mock_airpatrol_client_config_flow) -> AsyncMock:
    """Mock an AirPatrol coordinator client."""
    return _mock_airpatrol_client_config_flow[2]


@pytest.fixture
def mock_airpatrol_client_config_flow(_mock_airpatrol_client_config_flow) -> AsyncMock:
    """Mock an AirPatrol config flow client."""
    return _mock_airpatrol_client_config_flow[1]


@pytest.fixture
def mock_airpatrol_client(_mock_airpatrol_client_config_flow) -> AsyncMock:
    """Mock an AirPatrol client."""
    return _mock_airpatrol_client_config_flow[0]


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
        entry_id=1,
        unique_id="test_user_id",
    )


DEFAULT_UNIT_ID = "test_unit_001"


@pytest.fixture
async def load_integration(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Load the integration."""

    async def _load_integration() -> None:
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        return mock_config_entry

    return _load_integration


@pytest.fixture
def get_data():
    """A factory fixture that returns a function to build unit data.

    This allows customizing the data for each test.
    """

    def _make_data(
        unit_id=DEFAULT_UNIT_ID,
        name="Living room",
        manufacturer="AirPatrol",
        model="apw",
        hwid="hw01",
        power="on",
        target_temp="22.000",
        mode="cool",
        fan_speed="max",
        swing="off",
        current_temp="22.5",
        current_humidity="45",
        climate=True,
    ):
        data = {
            "unit_id": unit_id,
            "name": name,
            "manufacturer": manufacturer,
            "model": model,
            "hwid": hwid,
            "climate": {
                "ParametersData": {
                    "PumpPower": power,
                    "PumpTemp": target_temp,
                    "PumpMode": mode,
                    "FanSpeed": fan_speed,
                    "Swing": swing,
                },
                "RoomTemp": current_temp,
                "RoomHumidity": current_humidity,
            },
        }
        if not climate:
            del data["climate"]
        return [data]

    return _make_data
