"""Test the slide_local config flow."""

from unittest.mock import AsyncMock

from goslideapi.goslideapi import (
    AuthenticationFailed,
    ClientConnectionError,
    ClientTimeoutError,
    DigestAuthCalcError,
)
import pytest

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.slide_local.const import CONF_INVERT_POSITION, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import HOST

from tests.common import MockConfigEntry

MOCK_DHCP_DATA = DhcpServiceInfo(
    ip="127.0.0.2", macaddress="001122334455", hostname="slide_123456"
)


async def test_user(
    hass: HomeAssistant, mock_slide_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
            CONF_API_VERSION: "2",
            CONF_INVERT_POSITION: False,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == HOST
    assert result2["data"][CONF_HOST] == HOST
    assert result2["data"][CONF_PASSWORD] == "pwd"
    assert result2["data"][CONF_API_VERSION] == 2
    assert result2["data"][CONF_INVERT_POSITION] is False
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ClientConnectionError, "cannot_connect"),
        (ClientTimeoutError, "cannot_connect"),
        (AuthenticationFailed, "invalid_auth"),
        (DigestAuthCalcError, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
    mock_slide_api: AsyncMock,
) -> None:
    """Test we can handle Form exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_slide_api.slide_info.side_effect = exception

    # tests with connection error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
            CONF_API_VERSION: "2",
            CONF_INVERT_POSITION: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == error

    # tests with all provided
    mock_slide_api.slide_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
            CONF_API_VERSION: "2",
            CONF_INVERT_POSITION: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PASSWORD] == "pwd"
    assert result["data"][CONF_API_VERSION] == 2
    assert result["data"][CONF_INVERT_POSITION] is False


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if the device is already setup."""

    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PASSWORD: "pwd",
            CONF_API_VERSION: "2",
            CONF_INVERT_POSITION: False,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp(
    hass: HomeAssistant, mock_slide_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test starting a flow from discovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=MOCK_DHCP_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.2",
            CONF_PASSWORD: "pwd",
            CONF_API_VERSION: "2",
            CONF_INVERT_POSITION: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "127.0.0.2"
    assert result["data"][CONF_HOST] == "127.0.0.2"
    assert result["result"].unique_id == "00:11:22:33:44:55"
