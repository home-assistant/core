"""Fixtures for Ambee integration tests."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from ambee import AirQuality, Pollen
import pytest

from homeassistant.components.ambee.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Home Sweet Home",
        domain=DOMAIN,
        data={CONF_LATITUDE: 52.42, CONF_LONGITUDE: 4.44, CONF_API_KEY: "example"},
        unique_id="unique_thingy",
    )


@pytest.fixture
def mock_ambee(aioclient_mock: AiohttpClientMocker):
    """Return a mocked Ambee client."""
    with patch("homeassistant.components.ambee.Ambee") as ambee_mock:
        client = ambee_mock.return_value
        client.air_quality = AsyncMock(
            return_value=AirQuality.from_dict(
                json.loads(load_fixture("ambee/air_quality.json"))
            )
        )
        client.pollen = AsyncMock(
            return_value=Pollen.from_dict(json.loads(load_fixture("ambee/pollen.json")))
        )
        yield ambee_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_ambee: MagicMock
) -> MockConfigEntry:
    """Set up the Ambee integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
