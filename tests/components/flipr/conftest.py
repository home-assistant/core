"""Common fixtures for the flipr tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.flipr.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

# Data for the mocked object returned via flipr_api client.
MOCK_DATE_TIME = datetime(2021, 2, 15, 9, 10, 32, tzinfo=dt_util.UTC)
MOCK_FLIPR_MEASURE = {
    "temperature": 10.5,
    "ph": 7.03,
    "chlorine": 0.23654886,
    "red_ox": 657.58,
    "date_time": MOCK_DATE_TIME,
    "ph_status": "TooLow",
    "chlorine_status": "Medium",
    "battery": 95.0,
}

MOCK_HUB_STATE_ON = {
    "state": True,
    "mode": "planning",
    "planning": "dummyplanningid",
}

MOCK_HUB_STATE_OFF = {
    "state": False,
    "mode": "manual",
    "planning": "dummyplanningid",
}

MOCK_HUB_MODE_MANUAL = {
    "state": False,
    "mode": "manual",
    "planning": "dummyplanningid",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.flipr.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock the config entry."""
    return MockConfigEntry(
        version=2,
        domain=DOMAIN,
        unique_id="toto@toto.com",
        data={
            CONF_EMAIL: "toto@toto.com",
            CONF_PASSWORD: "myPassword",
        },
    )


@pytest.fixture
def mock_flipr_client() -> Generator[AsyncMock]:
    """Mock a Flipr client."""

    with (
        patch(
            "homeassistant.components.flipr.FliprAPIRestClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.flipr.config_flow.FliprAPIRestClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        # Default values for the tests using this mock :
        client.search_all_ids.return_value = {"flipr": ["myfliprid"], "hub": []}

        client.get_pool_measure_latest.return_value = MOCK_FLIPR_MEASURE

        client.get_hub_state.return_value = MOCK_HUB_STATE_ON

        client.set_hub_state.return_value = MOCK_HUB_STATE_ON

        client.set_hub_mode.return_value = MOCK_HUB_MODE_MANUAL

        yield client
