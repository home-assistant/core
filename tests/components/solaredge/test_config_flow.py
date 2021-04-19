"""Tests for the SolarEdge config flow."""
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant import data_entry_flow
from homeassistant.components.solaredge import config_flow
from homeassistant.components.solaredge.const import CONF_SITE_ID, DEFAULT_NAME
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

NAME = "solaredge site 1 2 3"
SITE_ID = "1a2b3c4d5e6f7g8h"
API_KEY = "a1b2c3d4e5f6g7h8"


@pytest.fixture(name="test_api")
def mock_controller():
    """Mock a successful Solaredge API."""
    api = Mock()
    api.get_details.return_value = {"details": {"status": "active"}}
    with patch("solaredge.Solaredge", return_value=api):
        yield api


def init_config_flow(hass: HomeAssistant) -> config_flow.SolarEdgeConfigFlow:
    """Init a configuration flow."""
    flow = config_flow.SolarEdgeConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass: HomeAssistant, test_api: Mock) -> None:
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # tets with all provided
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solaredge_site_1_2_3"
    assert result["data"][CONF_SITE_ID] == SITE_ID
    assert result["data"][CONF_API_KEY] == API_KEY


async def test_import(hass: HomeAssistant, test_api: Mock) -> None:
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


async def test_abort_if_already_setup(hass: HomeAssistant, test_api: str) -> None:
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
    assert result["reason"] == "already_configured"

    # user: Should fail, same SITE_ID
    result = await flow.async_step_user(
        {CONF_NAME: "test", CONF_SITE_ID: SITE_ID, CONF_API_KEY: "test"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_SITE_ID: "already_configured"}


async def test_asserts(hass: HomeAssistant, test_api: Mock) -> None:
    """Test the _site_in_configuration_exists method."""
    flow = init_config_flow(hass)

    # test with inactive site
    test_api.get_details.return_value = {"details": {"status": "NOK"}}
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_SITE_ID: "site_not_active"}

    # test with api_failure
    test_api.get_details.return_value = {}
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_SITE_ID: "invalid_api_key"}

    # test with ConnectionTimeout
    test_api.get_details.side_effect = ConnectTimeout()
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_SITE_ID: "could_not_connect"}

    # test with HTTPError
    test_api.get_details.side_effect = HTTPError()
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_SITE_ID: "could_not_connect"}
