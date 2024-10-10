"""Common fixtures for the OSO Energy tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from apyosoenergyapi.waterheater import OSOEnergyWaterHeaterData
import pytest

from homeassistant.components.osoenergy.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonObjectType

from tests.common import MockConfigEntry, load_json_object_fixture

MOCK_CONFIG = {
    CONF_API_KEY: "secret_api_key",
}
TEST_USER_EMAIL = "test_user_email@domain.com"


@pytest.fixture
def water_heater_fixture() -> JsonObjectType:
    """Load the water heater fixture."""
    return load_json_object_fixture("water_heater.json", DOMAIN)


@pytest.fixture
def mock_water_heater(water_heater_fixture) -> MagicMock:
    """Water heater mock object."""
    mock_heater = MagicMock(OSOEnergyWaterHeaterData)
    for key, value in water_heater_fixture.items():
        setattr(mock_heater, key, value)
    return mock_heater


@pytest.fixture
def mock_entry_data() -> dict[str, Any]:
    """Mock config entry data for fixture."""
    return MOCK_CONFIG


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_entry_data: dict[str, Any]
) -> ConfigEntry:
    """Mock a config entry setup for incomfort integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=mock_entry_data)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mock_osoenergy_client(mock_water_heater) -> Generator[AsyncMock]:
    """Mock a OSO Energy client."""

    with (
        patch(
            "homeassistant.components.osoenergy.OSOEnergy", MagicMock()
        ) as mock_client,
        patch(
            "homeassistant.components.osoenergy.config_flow.OSOEnergy", new=mock_client
        ),
    ):
        mock_session = MagicMock()
        mock_session.device_list = {"water_heater": [mock_water_heater]}
        mock_session.start_session = AsyncMock(
            return_value={"water_heater": [mock_water_heater]}
        )
        mock_session.update_data = AsyncMock(return_value=True)

        mock_client().session = mock_session

        mock_hotwater = MagicMock()
        mock_hotwater.get_water_heater = AsyncMock(return_value=mock_water_heater)
        mock_hotwater.set_profile = AsyncMock(return_value=True)
        mock_hotwater.set_v40_min = AsyncMock(return_value=True)
        mock_hotwater.turn_on = AsyncMock(return_value=True)
        mock_hotwater.turn_off = AsyncMock(return_value=True)

        mock_client().hotwater = mock_hotwater

        mock_client().get_user_email = AsyncMock(return_value=TEST_USER_EMAIL)
        mock_client().start_session = AsyncMock(
            return_value={"water_heater": [mock_water_heater]}
        )

        yield mock_client
