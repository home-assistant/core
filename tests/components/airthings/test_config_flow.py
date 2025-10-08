"""Test the Airthings config flow."""

from unittest.mock import AsyncMock

import airthings
import pytest

from homeassistant.components.airthings.const import CONF_SECRET, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_ID: "client_id",
    CONF_SECRET: "secret",
}

DHCP_SERVICE_INFO = [
    DhcpServiceInfo(
        hostname="airthings-view",
        ip="192.168.1.100",
        macaddress="000000000000",
    ),
    DhcpServiceInfo(
        hostname="airthings-hub",
        ip="192.168.1.101",
        macaddress="d01411900000",
    ),
    DhcpServiceInfo(
        hostname="airthings-hub",
        ip="192.168.1.102",
        macaddress="70b3d52a0000",
    ),
]


async def test_full_flow(
    hass: HomeAssistant, mock_airthings_token: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the full flow working."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airthings"
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == "client_id"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (airthings.AirthingsAuthError, "invalid_auth"),
        (airthings.AirthingsConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_exceptions(
    hass: HomeAssistant,
    mock_airthings_token: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle exceptions correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_airthings_token.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_airthings_token.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_entry_already_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user input for config_entry that already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("dhcp_service_info", DHCP_SERVICE_INFO)
async def test_dhcp_flow(
    hass: HomeAssistant,
    dhcp_service_info: DhcpServiceInfo,
    mock_airthings_token: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the DHCP discovery flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=dhcp_service_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airthings"
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_DATA[CONF_ID]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_flow_hub_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that DHCP discovery fails when already configured."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_SERVICE_INFO[0],
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
