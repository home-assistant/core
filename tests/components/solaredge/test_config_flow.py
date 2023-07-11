"""Tests for the SolarEdge config flow."""
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant import data_entry_flow
from homeassistant.components.solaredge.const import CONF_SITE_ID, DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER
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


async def test_user(hass: HomeAssistant, test_api: Mock) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result.get("title") == "solaredge_site_1_2_3"

    data = result.get("data")
    assert data
    assert data[CONF_SITE_ID] == SITE_ID
    assert data[CONF_API_KEY] == API_KEY


async def test_abort_if_already_setup(hass: HomeAssistant, test_api: str) -> None:
    """Test we abort if the site_id is already setup."""
    MockConfigEntry(
        domain="solaredge",
        data={CONF_NAME: DEFAULT_NAME, CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    ).add_to_hass(hass)

    # user: Should fail, same SITE_ID
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: "test", CONF_SITE_ID: SITE_ID, CONF_API_KEY: "test"},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {CONF_SITE_ID: "already_configured"}


async def test_ignored_entry_does_not_cause_error(
    hass: HomeAssistant, test_api: str
) -> None:
    """Test an ignored entry does not cause and error and we can still create an new entry."""
    MockConfigEntry(
        domain="solaredge",
        data={CONF_NAME: DEFAULT_NAME, CONF_API_KEY: API_KEY},
        source=SOURCE_IGNORE,
    ).add_to_hass(hass)

    # user: Should fail, same SITE_ID
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: "test", CONF_SITE_ID: SITE_ID, CONF_API_KEY: "test"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"

    data = result["data"]
    assert data
    assert data[CONF_SITE_ID] == SITE_ID
    assert data[CONF_API_KEY] == "test"


async def test_asserts(hass: HomeAssistant, test_api: Mock) -> None:
    """Test the _site_in_configuration_exists method."""

    # test with inactive site
    test_api.get_details.return_value = {"details": {"status": "NOK"}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {CONF_SITE_ID: "site_not_active"}

    # test with api_failure
    test_api.get_details.return_value = {}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {CONF_SITE_ID: "invalid_api_key"}

    # test with ConnectionTimeout
    test_api.get_details.side_effect = ConnectTimeout()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {CONF_SITE_ID: "could_not_connect"}

    # test with HTTPError
    test_api.get_details.side_effect = HTTPError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: NAME, CONF_API_KEY: API_KEY, CONF_SITE_ID: SITE_ID},
    )
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("errors") == {CONF_SITE_ID: "could_not_connect"}
