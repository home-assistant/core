"""Configure tests for openSenseMap."""
from collections.abc import AsyncGenerator
import re
from unittest.mock import AsyncMock, patch

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError
import pytest

from homeassistant.components.opensensemap.const import CONF_STATION_ID, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from . import VALID_STATION_ID, VALID_STATION_NAME

from tests.common import MockConfigEntry, load_json_object_fixture

ContextualizedEntry = AsyncGenerator[MockConfigEntry, None, None]


@pytest.fixture(name="valid_config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture to create a mock configuration entry for a valid OpenSenseMap station in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=VALID_STATION_NAME,
        data={CONF_STATION_ID: VALID_STATION_ID, CONF_NAME: VALID_STATION_NAME},
        unique_id=VALID_STATION_ID,
    )


@pytest.fixture(name="invalid_config_entry")
def mock_config_entry_invalid_id() -> MockConfigEntry:
    """Fixture to create a mock configuration entry with an invalid station id."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="INVALID STATION",
        data={
            CONF_STATION_ID: "INVALID_ID",
        },
        unique_id="INVALID_ID",
    )


@pytest.fixture(name="setup_entry_mock")
def patch_setup_entry() -> AsyncMock:
    """Fixture to patch the `async_setup_entry` method in the OpenSenseMap component."""
    return patch(
        "homeassistant.components.opensensemap.async_setup_entry", return_value=True
    )


@pytest.fixture(name="osm_api_mock")
def patch_opensensemap_get_data() -> AsyncMock:
    """Fixture to patch the `get_data` method of the OpenSenseMap API client."""

    async def get_fixture_data(self):
        provided_station_id = re.search(r"\/([^/]*)$", self.base_url).group(1)
        to_take = "valid" if provided_station_id == VALID_STATION_ID else "invalid"
        self.data = load_json_object_fixture(f"opensensemap/{to_take}.json")

    mock = patch.object(OpenSenseMap, "get_data", get_fixture_data)
    return mock


@pytest.fixture(name="osm_api_failed_mock")
def patch_opensensemap_connection_failed() -> AsyncMock:
    """Fixture to patch the `get_data` method of the OpenSenseMap API client to simulate a connection error."""
    return patch.object(OpenSenseMap, "get_data", side_effect=OpenSenseMapError)


@pytest.fixture(name="loaded_config_entry")
async def mock_setup_integration(
    hass: HomeAssistant,
    valid_config_entry: MockConfigEntry,
    osm_api_mock: AsyncMock,
) -> ContextualizedEntry:
    """Asynchronous fixture to set up a valid OpenSenseMap configuration entry in Home Assistant."""

    valid_config_entry.add_to_hass(hass)
    with osm_api_mock:
        assert await hass.config_entries.async_setup(valid_config_entry.entry_id)
        await hass.async_block_till_done()
        yield valid_config_entry
