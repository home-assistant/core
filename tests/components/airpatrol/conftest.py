"""Common fixtures for the AirPatrol tests."""

from unittest.mock import MagicMock, patch

from airpatrol.api import AirPatrolAPI
import pytest

from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.conftest import MockConfigEntry


@pytest.fixture
def mock_api_response():
    """Mock AirPatrol API response."""
    with patch(
        "airpatrol.api.AirPatrolAPI.get_data",
    ) as mock_response:
        yield mock_response


@pytest.fixture
def mock_api_set_climate_data():
    """Mock AirPatrol API set temperature."""
    with patch(
        "airpatrol.api.AirPatrolAPI.set_unit_climate_data",
    ) as mock_set_temp:
        yield mock_set_temp


@pytest.fixture
def mock_api_authentication(mock_api):
    """Mock AirPatrol API authentication success."""
    with patch("airpatrol.api.AirPatrolAPI.authenticate", autospec=True) as mock_auth:
        mock_auth.return_value = mock_api
        yield mock_auth


@pytest.fixture
def mock_api():
    """Mock AirPatrol API."""
    api = MagicMock(spec=AirPatrolAPI)
    api.get_unique_id.return_value = "test_user_id"
    api.get_access_token.return_value = "test_access_token"
    return api


@pytest.fixture
def mock_config_entry():
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
