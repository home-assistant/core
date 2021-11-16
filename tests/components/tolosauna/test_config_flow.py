"""Tests for the TOLO Sauna config flow."""
from unittest.mock import Mock, patch

import pytest
from tololib.errors import ResponseTimedOutError

from homeassistant.components.dhcp import IP_ADDRESS, MAC_ADDRESS
from homeassistant.components.tolosauna.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

MOCK_DHCP_DATA = {IP_ADDRESS: "127.0.0.2", MAC_ADDRESS: "00:11:22:33:44:55"}


@pytest.fixture(name="toloclient")
def toloclient_fixture() -> Mock:
    """Patch libraries."""
    with patch(
        "homeassistant.components.tolosauna.config_flow.ToloClient"
    ) as toloclient:
        yield toloclient


async def test_user_no_input(hass: HomeAssistant):
    """Test starting a flow by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_user_with_valid_host(hass: HomeAssistant, toloclient: Mock):
    """Test a user initiated config flow with provided host."""
    toloclient().get_status_info.side_effect = lambda *args, **kwargs: object()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "TOLO Sauna"
    assert result["data"][CONF_HOST] == "127.0.0.1"


async def test_user_with_unreachable_host(hass: HomeAssistant, toloclient: Mock):
    """Test a user initiated config flow with provided host which is not reachable."""
    toloclient().get_status_info.side_effect = lambda *args, **kwargs: None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_with_timed_out_host(hass: HomeAssistant, toloclient: Mock):
    """Test a user initiated config flow with provided host which times out."""
    toloclient().get_status_info.side_effect = lambda *args, **kwargs: (
        _ for _ in ()
    ).throw(ResponseTimedOutError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": "cannot_connect"}


async def test_dhcp(hass: HomeAssistant, toloclient: Mock):
    """Test starting a flow from discovery."""
    toloclient().get_status_info.side_effect = lambda *args, **kwargs: object()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=MOCK_DHCP_DATA
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "TOLO Sauna"
    assert result["data"][CONF_HOST] == "127.0.0.2"
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_dhcp_invalid_device(hass: HomeAssistant, toloclient: Mock):
    """Test starting a flow from discovery."""
    toloclient().get_status_info.side_effect = lambda *args, **kwargs: None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=MOCK_DHCP_DATA
    )
    assert result["type"] == RESULT_TYPE_ABORT
