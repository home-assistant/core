"""Define fixtures for Flu Near You tests."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.flunearyou.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }


@pytest.fixture(name="data_cdc", scope="session")
def data_cdc_fixture():
    """Define CDC data."""
    return json.loads(load_fixture("cdc_data.json", "flunearyou"))


@pytest.fixture(name="data_user", scope="session")
def data_user_fixture():
    """Define user data."""
    return json.loads(load_fixture("user_data.json", "flunearyou"))


@pytest.fixture(name="setup_flunearyou")
async def setup_flunearyou_fixture(hass, data_cdc, data_user, config):
    """Define a fixture to set up Flu Near You."""
    with patch(
        "pyflunearyou.cdc.CdcReport.status_by_coordinates", return_value=data_cdc
    ), patch(
        "pyflunearyou.user.UserReport.status_by_coordinates", return_value=data_user
    ), patch(
        "homeassistant.components.flunearyou.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "51.528308, -0.3817765"
