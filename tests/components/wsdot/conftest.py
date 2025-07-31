"""Provide common WSDOT fixtures."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from wsdot import TravelTime

from homeassistant.components.wsdot.const import CONF_TRAVEL_TIMES, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_travel_time() -> Generator[TravelTime]:
    """WsdotTravelTimes.get_travel_time is mocked to return a TravelTime data based on test fixture payload."""
    with patch("wsdot.WsdotTravelTimes", autospec=True) as mock:
        client = mock.return_value
        response = TravelTime(**load_json_object_fixture("wsdot.json", DOMAIN))
        client.get_travel_time.return_value = response
        client.get_all_travel_times.return_value = [response]
        yield mock


@pytest.fixture
def mock_config_data() -> dict[str, Any]:
    """Return valid test config data."""
    return {
        CONF_API_KEY: "foo",
        CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I90 EB"}],
    }


@pytest.fixture
def mock_config_entry(mock_config_data) -> MockConfigEntry:
    """Mock a wsdot config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_data: MockConfigEntry,
    subentries: list[dict[str, Any]],
) -> MockConfigEntry:
    """Set up wsdot integration with subentries for testing."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        subentries_data=subentries,
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
