"""Test the Sunsynk config flow."""

from unittest.mock import AsyncMock

import pytest
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError

from homeassistant.components.sunsynk.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import PASSWORD, USER_ID, USERNAME

from tests.common import MockConfigEntry

DHCP_SERVICE_INFO = DhcpServiceInfo(
    hostname="e-linter", ip="192.168.1.20", macaddress="1091a8aabbcc"
)


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"] == {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    assert result["result"].unique_id == USER_ID
    assert len(mock_sunsynk_client.get_user.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_sunsynk_client", "mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the account is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "other@example.com", CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(SunsynkAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(SunsynkConnectionError, "cannot_connect", id="cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_sunsynk_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test the user flow shows an error and can recover."""
    mock_sunsynk_client.get_user.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_sunsynk_client.get_user.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
