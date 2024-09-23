"""Configure tests for the OpenSky integration."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest
from python_opensky import StatesResponse

from homeassistant.components.opensky.const import (
    CONF_ALTITUDE,
    CONF_CONTRIBUTING_USER,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_RADIUS,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opensky.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create OpenSky entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OpenSky",
        data={
            CONF_LATITUDE: 0.0,
            CONF_LONGITUDE: 0.0,
        },
        options={
            CONF_RADIUS: 10.0,
            CONF_ALTITUDE: 0.0,
        },
    )


@pytest.fixture(name="config_entry_altitude")
def mock_config_entry_altitude() -> MockConfigEntry:
    """Create Opensky entry with altitude in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OpenSky",
        data={
            CONF_LATITUDE: 0.0,
            CONF_LONGITUDE: 0.0,
        },
        options={
            CONF_RADIUS: 10.0,
            CONF_ALTITUDE: 12500.0,
        },
    )


@pytest.fixture(name="config_entry_authenticated")
def mock_config_entry_authenticated() -> MockConfigEntry:
    """Create authenticated Opensky entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OpenSky",
        data={
            CONF_LATITUDE: 0.0,
            CONF_LONGITUDE: 0.0,
        },
        options={
            CONF_RADIUS: 10.0,
            CONF_ALTITUDE: 12500.0,
            CONF_USERNAME: "asd",
            CONF_PASSWORD: "secret",
            CONF_CONTRIBUTING_USER: True,
        },
    )


@pytest.fixture
async def opensky_client() -> AsyncGenerator[AsyncMock]:
    """Mock the OpenSky client."""
    with (
        patch(
            "homeassistant.components.opensky.OpenSky",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.opensky.config_flow.OpenSky",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_states.return_value = StatesResponse.from_api(
            load_json_object_fixture("states.json", DOMAIN)
        )
        client.is_authenticated = False
        yield client
