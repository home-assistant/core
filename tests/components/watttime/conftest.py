"""Define test fixtures for WattTime."""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.watttime.config_flow import (
    CONF_LOCATION_TYPE,
    LOCATION_TYPE_COORDINATES,
)
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
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="client")
def client_fixture(get_grid_region, data_realtime_emissions):
    """Define an aiowatttime client."""
    client = Mock()
    client.emissions.async_get_grid_region = get_grid_region
    client.emissions.async_get_realtime_emissions = AsyncMock(
        return_value=data_realtime_emissions
    )
    return client


@pytest.fixture(name="config_auth")
def config_auth_fixture(hass):
    """Define an auth config entry data fixture."""
    return {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "password",
    }


@pytest.fixture(name="config_coordinates")
def config_coordinates_fixture(hass):
    """Define a coordinates config entry data fixture."""
    return {
        CONF_LATITUDE: 32.87336,
        CONF_LONGITUDE: -117.22743,
    }


@pytest.fixture(name="config_location_type")
def config_location_type_fixture(hass):
    """Define a location type config entry data fixture."""
    return {
        CONF_LOCATION_TYPE: LOCATION_TYPE_COORDINATES,
    }


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config_auth, config_coordinates):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=(
            f"{config_coordinates[CONF_LATITUDE]}, {config_coordinates[CONF_LONGITUDE]}"
        ),
        data={
            **config_auth,
            **config_coordinates,
            CONF_BALANCING_AUTHORITY: "PJM New Jersey",
            CONF_BALANCING_AUTHORITY_ABBREV: "PJM_NJ",
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


@pytest.fixture(name="get_grid_region")
def get_grid_region_fixture(data_grid_region):
    """Define an aiowatttime method to get grid region data."""
    return AsyncMock(return_value=data_grid_region)


@pytest.fixture(name="setup_watttime")
async def setup_watttime_fixture(hass, client, config_auth, config_coordinates):
    """Define a fixture to set up WattTime."""
    with patch(
        "homeassistant.components.watttime.Client.async_login", return_value=client
    ), patch(
        "homeassistant.components.watttime.config_flow.Client.async_login",
        return_value=client,
    ), patch("homeassistant.components.watttime.PLATFORMS", []):
        assert await async_setup_component(
            hass, DOMAIN, {**config_auth, **config_coordinates}
        )
        await hass.async_block_till_done()
        yield
