"""Tests for the SolarEdge config flow."""
import pytest
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.solaredge import config_flow
from homeassistant.components.solaredge.const import CONF_SITE_ID, DEFAULT_NAME
from homeassistant.const import CONF_NAME, CONF_API_KEY

from tests.common import MockConfigEntry

NAME = "solaredge site 1 2 3"
SITE_ID = "1a2b3c4d5e6f7g8h"
API_KEY = "a1b2c3d4e5f6g7h8"


@pytest.fixture(name="test_connect")
def mock_controller():
    """Mock a successfull _check_site."""
    with patch(
        "homeassistant.components.solaredge.config_flow.SolarEdgeConfigFlow._check_site",
        return_value=True,
    ):
        yield


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.SolarEdgeConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass, test_connect):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # tets with all provided
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID}
    )
    print(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solaredge_site_1_2_3"
    assert result["data"][CONF_SITE_ID] == SITE_ID
    assert result["data"][CONF_API_KEY] == API_KEY


async def test_import(hass, test_connect):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with site_id and api_key
    result = await flow.async_step_import(
        {CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solaredge"
    assert result["data"][CONF_SITE_ID] == SITE_ID
    assert result["data"][CONF_API_KEY] == API_KEY

    # import with all
    result = await flow.async_step_import(
        {CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID, CONF_NAME: NAME}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solaredge_site_1_2_3"
    assert result["data"][CONF_SITE_ID] == SITE_ID
    assert result["data"][CONF_API_KEY] == API_KEY


async def test_abort_if_already_setup(hass, test_connect):
    """Test we abort if the site_id is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain="solaredge",
        data={CONF_NAME: DEFAULT_NAME, CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    ).add_to_hass(hass)

    # import: Should fail, same SITE_ID
    result = await flow.async_step_import(
        {CONF_NAME: DEFAULT_NAME, CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "site_exists"

    # user: Should fail, same SITE_ID
    result = await flow.async_step_user(
        {CONF_NAME: "test", CONF_SITE_ID: SITE_ID, CONF_API_KEY: "test"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_SITE_ID: "site_exists"}
