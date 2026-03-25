"""Fixtures for Zamg integration tests."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

import pytest
from zamg import ZamgData as ZamgDevice

from homeassistant.components.zamg.const import CONF_STATION_ID, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_STATION_ID = "11240"
TEST_STATION_NAME = "Graz/Flughafen"

TEST_STATION_ID_2 = "11035"
TEST_STATION_NAME_2 = "WIEN/HOHE WARTE"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATION_ID: TEST_STATION_ID},
        unique_id=TEST_STATION_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.zamg.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_zamg_config_flow() -> Generator[MagicMock]:
    """Return a mocked Zamg client."""
    with patch(
        "homeassistant.components.zamg.sensor.ZamgData", autospec=True
    ) as zamg_mock:
        zamg = zamg_mock.return_value
        zamg.update.return_value = ZamgDevice(
            json.loads(load_fixture("zamg/data.json"))
        )
        zamg.get_data.return_value = zamg.get_data(TEST_STATION_ID)
        yield zamg


@pytest.fixture
def mock_zamg() -> Generator[MagicMock]:
    """Return a mocked Zamg client."""

    with patch(
        "homeassistant.components.zamg.config_flow.ZamgData", autospec=True
    ) as zamg_mock:
        zamg = zamg_mock.return_value
        zamg.update.return_value = {TEST_STATION_ID: {"Name": TEST_STATION_NAME}}
        zamg.zamg_stations.return_value = {
            TEST_STATION_ID: (46.99305556, 15.43916667, TEST_STATION_NAME),
            "11244": (46.8722229, 15.90361118, "BAD GLEICHENBERG"),
        }
        zamg.closest_station.return_value = TEST_STATION_ID
        zamg.get_data.return_value = TEST_STATION_ID
        zamg.get_station_name = TEST_STATION_NAME
        yield zamg


@pytest.fixture
def mock_zamg_coordinator() -> Generator[MagicMock]:
    """Return a mocked Zamg client."""

    with patch(
        "homeassistant.components.zamg.coordinator.ZamgDevice", autospec=True
    ) as zamg_mock:
        zamg = zamg_mock.return_value
        zamg.update.return_value = {TEST_STATION_ID: {"Name": TEST_STATION_NAME}}
        zamg.zamg_stations.return_value = {
            TEST_STATION_ID: (46.99305556, 15.43916667, TEST_STATION_NAME),
            "11244": (46.8722229, 15.90361118, "BAD GLEICHENBERG"),
        }
        zamg.closest_station.return_value = TEST_STATION_ID
        zamg.get_data.return_value = TEST_STATION_ID
        zamg.get_station_name = TEST_STATION_NAME
        yield zamg


@pytest.fixture
async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Zamg integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
