"""Define test fixtures for WattTime."""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.watttime.const import (
    CONF_BALANCING_AUTHORITY,
    CONF_BALANCING_AUTHORITY_ABBREV,
    DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_BALANCING_AUTHORITY = "PJM New Jersey"
TEST_BALANCING_AUTHORITY_ABBREV = "PJM_NJ"
TEST_LATITUDE = 32.87336
TEST_LONGITUDE = -117.22743
TEST_PASSWORD = "password"
TEST_USERNAME = "user"


@pytest.fixture(name="client")
def client_fixture(data_grid_region, data_realtime_emissions):
    """Define an aiowatttime client."""
    return Mock(
        emissions=Mock(
            async_get_grid_region=AsyncMock(return_value=data_grid_region),
            async_get_realtime_emissions=AsyncMock(
                return_value=data_realtime_emissions
            ),
        )
    )


@pytest.fixture(name="config_auth")
def config_auth_fixture():
    """Define an auth config entry data fixture."""
    return {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


@pytest.fixture(name="config_coordinates")
def config_coordinates_fixture():
    """Define a coordinates config entry data fixture."""
    return {
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
    }


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config_auth, config_coordinates):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=(
            f"{config_coordinates[CONF_LATITUDE]}, {config_coordinates[CONF_LONGITUDE]}"
        ),
        data={
            **config_auth,
            **config_coordinates,
            CONF_BALANCING_AUTHORITY: TEST_BALANCING_AUTHORITY,
            CONF_BALANCING_AUTHORITY_ABBREV: TEST_BALANCING_AUTHORITY_ABBREV,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="data_grid_region", scope="package")
def data_grid_region_fixture():
    """Define grid region data."""
    return json.loads(load_fixture("grid_region_data.json", "watttime"))


@pytest.fixture(name="data_realtime_emissions", scope="package")
def data_realtime_emissions_fixture():
    """Define realtime emissions data."""
    return json.loads(load_fixture("realtime_emissions_data.json", "watttime"))


@pytest.fixture(name="mock_aiowatttime")
async def mock_aiowatttime_fixture(client, config_auth, config_coordinates):
    """Define a fixture to patch aiowatttime."""
    with patch(
        "homeassistant.components.watttime.Client.async_login", return_value=client
    ), patch(
        "homeassistant.components.watttime.config_flow.Client.async_login",
        return_value=client,
    ):
        yield


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(
    hass: HomeAssistant, config_entry, mock_aiowatttime
):
    """Define a fixture to set up watttime."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return
