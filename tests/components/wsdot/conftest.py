"""Provide common WSDOT fixtures."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from wsdot import TravelTime, WsdotTravelError

from homeassistant.components.wsdot.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_travel_time() -> Generator[AsyncMock]:
    """WsdotTravelTimes.get_travel_time is mocked to return a TravelTime data based on test fixture payload."""
    with (
        patch(
            "homeassistant.components.wsdot.wsdot_api.WsdotTravelTimes", autospec=True
        ) as mock,
        patch(
            "homeassistant.components.wsdot.config_flow.wsdot_api.WsdotTravelTimes",
            new=mock,
        ),
    ):
        client = mock.return_value
        response = TravelTime(**load_json_object_fixture("wsdot.json", DOMAIN))
        client.get_travel_time.return_value = response
        client.get_all_travel_times.return_value = [response]
        yield client


@pytest.fixture
def failed_travel_time_status() -> int:
    """Return the default status code for failed travel time requests."""
    return 400


@pytest.fixture
def mock_failed_travel_time(
    mock_travel_time: AsyncMock, failed_travel_time_status: int
) -> AsyncMock:
    """WsdotTravelTimes.get_travel_time is mocked to raise a WsdotTravelError."""
    mock_travel_time.get_travel_time.side_effect = WsdotTravelError(
        status=failed_travel_time_status
    )
    mock_travel_time.get_all_travel_times.side_effect = WsdotTravelError(
        status=failed_travel_time_status
    )
    return mock_travel_time


@pytest.fixture
def mock_config_data() -> dict[str, Any]:
    """Return valid test config data."""
    return {
        CONF_API_KEY: "abcd-1234",
    }


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryData]:
    """Mock subentries."""
    return [
        ConfigSubentryData(
            subentry_type="travel_time",
            title="I-90 EB",
            unique_id="96",
            data={
                CONF_ID: 96,
                CONF_NAME: "Seattle-Bellevue via I-90 (EB AM)",
            },
        )
    ]


@pytest.fixture
def mock_config_entry(
    mock_config_data: dict[str, Any], mock_subentries: list[ConfigSubentryData]
) -> MockConfigEntry:
    """Mock a wsdot config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        subentries_data=mock_subentries,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up wsdot integration with subentries for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock config entry setup."""
    with patch(
        "homeassistant.components.wsdot.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
