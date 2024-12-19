"""Tests for the We Connect config flow."""

from copy import deepcopy
from unittest.mock import patch

from weconnect.errors import APIError, AuthentificationError

from homeassistant import config_entries
from homeassistant.components.weconnect.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG_DATA, MOCK_CONFIG_ENTRY
from .conftest import mock_weconnect_login

from tests.common import MockConfigEntry


async def test_successful_login(hass: HomeAssistant) -> None:
    """Test Config Flow with successful login."""
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "user"

    with patch(
        "weconnect.weconnect.WeConnect.login",
        mock_weconnect_login,
    ):
        flow = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            MOCK_CONFIG_DATA,
        )

        assert flow["type"] is FlowResultType.CREATE_ENTRY
        assert flow["title"] == MOCK_CONFIG_DATA[CONF_USERNAME]
        assert flow["data"] == MOCK_CONFIG_DATA


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test Config Flow with invalid authentication error."""
    with patch(
        "weconnect.weconnect.WeConnect.login",
        side_effect=AuthentificationError,
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_CONFIG_DATA,
        )

        assert flow["type"] is FlowResultType.FORM
        assert flow["step_id"] == "user"
        assert flow["errors"] == {"base": "invalid_auth"}


async def test_api_error(hass: HomeAssistant) -> None:
    """Test Config Flow with general connection error."""
    with patch(
        "weconnect.weconnect.WeConnect.login",
        side_effect=APIError,
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_CONFIG_DATA,
        )

        assert flow["type"] is FlowResultType.FORM
        assert flow["step_id"] == "user"
        assert flow["errors"] == {"base": "cannot_connect"}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test Config Flow with re-authentication."""
    mock_config_entry_wrong_password = deepcopy(MOCK_CONFIG_ENTRY)
    mock_config_entry_wrong_password["data"][CONF_PASSWORD] = "wrong"

    config_entry = MockConfigEntry(**mock_config_entry_wrong_password)
    config_entry.add_to_hass(hass)

    with patch(
        "weconnect.weconnect.WeConnect.login",
        side_effect=AuthentificationError,
    ) as mock_login:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.data == mock_config_entry_wrong_password["data"]
        assert config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR

        reauth_flow = await config_entry.start_reauth_flow(hass)
        assert reauth_flow["type"] is FlowResultType.FORM
        assert reauth_flow["step_id"] == "user"

        mock_login.side_effect = None
        mock_login.return_value = True

        reconfigure_flow = await hass.config_entries.flow.async_configure(
            reauth_flow["flow_id"], MOCK_CONFIG_DATA
        )
        await hass.async_block_till_done()

        assert reconfigure_flow["type"] is FlowResultType.ABORT
        assert reconfigure_flow["reason"] == "reauth_successful"
        assert config_entry.data == MOCK_CONFIG_ENTRY["data"]
