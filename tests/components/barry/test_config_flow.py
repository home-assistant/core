"""Tests for Barry config flow."""
from unittest.mock import MagicMock, patch

from pybarry import InvalidToken
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.barry import config_flow
from homeassistant.components.barry.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import MockConfigEntry

test_data = {
    CONF_ACCESS_TOKEN: "valid",
}


@pytest.fixture(name="barry_setup", autouse=True)
def barry_setup_fixture():
    """Patch Barry setup entry."""
    with patch("homeassistant.components.barry.async_setup_entry", return_value=True):
        yield


async def test_show_config_form(hass):
    """Test show configuration form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_invalid_access_token(hass):
    """Test that errors are shown when API key is invalid."""
    with patch(
        "pybarry.Barry.get_all_metering_points",
        side_effect=InvalidToken("Invalid access token"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=test_data,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {CONF_ACCESS_TOKEN: "invalid_access_token"}


async def test_unknown_error(hass):
    """Test that errors are shown when something went wrong."""
    with patch(
        "pybarry.Barry.get_all_metering_points",
        side_effect=Exception("Unexpected error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=test_data,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {CONF_ACCESS_TOKEN: "unknown"}


async def test_create_entry(hass):
    """Test create entry from user input."""
    with patch(
        "pybarry.Barry.get_all_metering_points", return_value=[("mpid", "code")]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=test_data
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "metering_point"

    flow = config_flow.BarryConfigFlow()
    flow.init_info = MagicMock()
    flow.init_info.get_all_metering_points.return_value = [("mpid", "code")]
    flow.context = {}
    type(flow.init_info).access_token = CONF_ACCESS_TOKEN
    flow.hass = hass
    user_input = {"metering_point": "mpid"}

    result = await flow.async_step_metering_point(user_input=user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["access_token"] == CONF_ACCESS_TOKEN
    assert result["data"]["price_code"] == "code"


async def test_user_config(hass):
    """Test user config."""
    flow = config_flow.BarryConfigFlow()
    flow.hass = hass
    user_input = {CONF_ACCESS_TOKEN: "valid"}

    result = await flow.async_step_import(user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_flow_entry_already_exists(hass):
    """Test user input for config_entry that already exists."""
    first_entry = MockConfigEntry(domain="barry", data={CONF_ACCESS_TOKEN: "valid"})
    first_entry.add_to_hass(hass)

    with patch("pybarry.Barry.get_all_metering_points", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=test_data
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
