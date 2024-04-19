"""Define test fixtures for AirVisual."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.airvisual import (
    CONF_CITY,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
)
from homeassistant.components.airvisual.config_flow import async_get_geography_id
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)

from tests.common import MockConfigEntry, load_fixture

TEST_API_KEY = "abcde12345"
TEST_LATITUDE = 51.528308
TEST_LONGITUDE = -0.3817765
TEST_LATITUDE2 = 37.514626
TEST_LONGITUDE2 = 127.057414

COORDS_CONFIG = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_LATITUDE: TEST_LATITUDE,
    CONF_LONGITUDE: TEST_LONGITUDE,
}

COORDS_CONFIG2 = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_LATITUDE: TEST_LATITUDE2,
    CONF_LONGITUDE: TEST_LONGITUDE2,
}

TEST_CITY = "Beijing"
TEST_STATE = "Beijing"
TEST_COUNTRY = "China"

NAME_CONFIG = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_CITY: TEST_CITY,
    CONF_STATE: TEST_STATE,
    CONF_COUNTRY: TEST_COUNTRY,
}


@pytest.fixture(name="cloud_api")
def cloud_api_fixture(data_cloud):
    """Define a mock CloudAPI object."""
    return Mock(
        air_quality=Mock(
            city=AsyncMock(return_value=data_cloud),
            nearest_city=AsyncMock(return_value=data_cloud),
        )
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, config_entry_version, integration_type):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
        unique_id=async_get_geography_id(config),
        data={**config, CONF_INTEGRATION_TYPE: integration_type},
        options={CONF_SHOW_ON_MAP: True},
        version=config_entry_version,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config_entry_version")
def config_entry_version_fixture():
    """Define a config entry version fixture."""
    return 2


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return COORDS_CONFIG


@pytest.fixture(name="data_cloud", scope="package")
def data_cloud_fixture():
    """Define an update coordinator data example."""
    return json.loads(load_fixture("data.json", "airvisual"))


@pytest.fixture(name="data_pro", scope="package")
def data_pro_fixture():
    """Define an update coordinator data example for the Pro."""
    return json.loads(load_fixture("data.json", "airvisual_pro"))


@pytest.fixture(name="integration_type")
def integration_type_fixture():
    """Define an integration type."""
    return INTEGRATION_TYPE_GEOGRAPHY_COORDS


@pytest.fixture(name="mock_pyairvisual")
async def mock_pyairvisual_fixture(cloud_api, node_samba):
    """Define a fixture to patch pyairvisual."""
    with (
        patch(
            "homeassistant.components.airvisual.CloudAPI",
            return_value=cloud_api,
        ),
        patch(
            "homeassistant.components.airvisual.config_flow.CloudAPI",
            return_value=cloud_api,
        ),
        patch(
            "homeassistant.components.airvisual_pro.NodeSamba",
            return_value=node_samba,
        ),
        patch(
            "homeassistant.components.airvisual_pro.config_flow.NodeSamba",
            return_value=node_samba,
        ),
    ):
        yield


@pytest.fixture(name="node_samba")
def node_samba_fixture(data_pro):
    """Define a mock NodeSamba object."""
    return Mock(
        async_connect=AsyncMock(),
        async_disconnect=AsyncMock(),
        async_get_latest_measurements=AsyncMock(return_value=data_pro),
    )


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass, config_entry, mock_pyairvisual):
    """Define a fixture to set up airvisual."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
