"""Define test fixtures for ReCollect Waste."""
from datetime import date
from unittest.mock import AsyncMock, Mock, patch

from aiorecollect.client import PickupEvent, PickupType
import pytest

from homeassistant.components.recollect_waste.const import (
    CONF_PLACE_ID,
    CONF_SERVICE_ID,
    DOMAIN,
)

from tests.common import MockConfigEntry

TEST_PLACE_ID = "12345"
TEST_SERVICE_ID = "67890"


@pytest.fixture(name="client")
def client_fixture(pickup_events):
    """Define a fixture to return a mocked aiopurple API object."""
    return Mock(async_get_pickup_events=AsyncMock(return_value=pickup_events))


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=f"{TEST_PLACE_ID}, {TEST_SERVICE_ID}", data=config
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_PLACE_ID: TEST_PLACE_ID,
        CONF_SERVICE_ID: TEST_SERVICE_ID,
    }


@pytest.fixture(name="pickup_events")
def pickup_events_fixture():
    """Define a list of pickup events."""
    return [
        PickupEvent(
            date(2022, 1, 23), [PickupType("garbage", "Trash Collection")], "The Sun"
        )
    ]


@pytest.fixture(name="mock_aiorecollect")
async def mock_aiorecollect_fixture(client):
    """Define a fixture to patch aiorecollect."""
    with patch(
        "homeassistant.components.recollect_waste.Client",
        return_value=client,
    ), patch(
        "homeassistant.components.recollect_waste.config_flow.Client",
        return_value=client,
    ):
        yield


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass, config_entry, mock_aiorecollect):
    """Define a fixture to set up recollect_waste."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
