"""Test the for the BMW Connected Drive config flow."""
from unittest.mock import patch

from bimmer_connected.api.authentication import MyBMWAuthentication
from httpx import HTTPError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.bmw_connected_drive.config_flow import DOMAIN
from homeassistant.components.bmw_connected_drive.const import (
    CONF_READ_ONLY,
    CONF_REFRESH_TOKEN,
)
from homeassistant.const import CONF_USERNAME

from . import FIXTURE_CONFIG_ENTRY, FIXTURE_REFRESH_TOKEN, FIXTURE_USER_INPUT

from tests.common import MockConfigEntry

FIXTURE_COMPLETE_ENTRY = FIXTURE_CONFIG_ENTRY["data"]
FIXTURE_IMPORT_ENTRY = {**FIXTURE_USER_INPUT, CONF_REFRESH_TOKEN: None}


def login_sideeffect(self: MyBMWAuthentication):
    """Mock logging in and setting a refresh token."""
    self.refresh_token = FIXTURE_REFRESH_TOKEN


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass):
    """Test we show user form on BMW connected drive connection error."""

    def _mock_get_oauth_token(*args, **kwargs):
        pass

    with patch(
        "bimmer_connected.api.authentication.MyBMWAuthentication.login",
        side_effect=HTTPError("login failure"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_full_user_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    with patch(
        "bimmer_connected.api.authentication.MyBMWAuthentication.login",
        side_effect=login_sideeffect,
        autospec=True,
    ), patch(
        "homeassistant.components.bmw_connected_drive.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=FIXTURE_USER_INPUT,
        )
        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2["title"] == FIXTURE_COMPLETE_ENTRY[CONF_USERNAME]
        assert result2["data"] == FIXTURE_COMPLETE_ENTRY

        assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow_implementation(hass):
    """Test config flow options."""
    with patch(
        "bimmer_connected.account.MyBMWAccount.get_vehicles",
        return_value=[],
    ), patch(
        "homeassistant.components.bmw_connected_drive.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "account_options"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_READ_ONLY: True},
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_READ_ONLY: True,
        }

        assert len(mock_setup_entry.mock_calls) == 1
