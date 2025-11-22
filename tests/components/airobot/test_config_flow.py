"""Test the Airobot config flow."""

from unittest.mock import AsyncMock

from pyairobotrest.exceptions import (
    AirobotAuthError,
    AirobotConnectionError,
    AirobotError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.airobot.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

TEST_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_USERNAME: "T01A1B2C3",
    CONF_PASSWORD: "test-password",
}


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
) -> None:
    """Test user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"] == TEST_USER_INPUT
    assert result["result"].unique_id == "T01A1B2C3"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (AirobotAuthError("Authentication failed"), "invalid_auth"),
        (AirobotConnectionError("Connection failed"), "cannot_connect"),
        (AirobotError("Generic error"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test we handle various errors in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_airobot_client.get_settings.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    mock_airobot_client.get_settings.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"] == TEST_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate detection."""
    mock_config_entry.add_to_hass(hass)

    # Try to configure the same device again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
) -> None:
    """Test DHCP discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="b8d61aabcdef",
            hostname="airobot-thermostat-t01a1b2c3",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"
    assert result["description_placeholders"] == {
        "host": "192.168.1.100",
        "device_id": "T01A1B2C3",
    }

    # Complete the flow by providing password only
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "test-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_USERNAME] == "T01A1B2C3"
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert result["data"][CONF_MAC] == "b8d61aabcdef"


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (AirobotAuthError("Invalid credentials"), "invalid_auth"),
        (AirobotConnectionError("Connection failed"), "cannot_connect"),
        (Exception("Unknown error"), "unknown"),
    ],
)
async def test_dhcp_discovery_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test DHCP discovery with error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="aabbccddeeff",
            hostname="airobot-thermostat-t01d4e5f6",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    mock_airobot_client.get_statuses.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "wrong"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Recover from error
    mock_airobot_client.get_statuses.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "test-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_duplicate(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery with duplicate device."""
    mock_config_entry.add_to_hass(hass)

    # DHCP discovers the same device with potentially different IP
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.101",  # Different IP
            macaddress="b8d61aabcdef",  # Same MAC
            hostname="airobot-thermostat-t01a1b2c3",  # Same hostname = same device_id
        ),
    )
    await hass.async_block_till_done()

    # Should abort immediately since device_id extracted from hostname matches existing entry
    # and update the IP address
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the IP was updated in the existing entry
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"
