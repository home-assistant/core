"""Test the Airobot config flow."""

from unittest.mock import AsyncMock

from pyairobotrest.exceptions import (
    AirobotAuthError,
    AirobotConnectionError,
    AirobotError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.airobot.const import CONF_MAC, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

TEST_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_USERNAME: "T01XXXXXX",
    CONF_PASSWORD: "test-password",
}


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"] == TEST_USER_INPUT
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
    mock_airobot_config_flow_client: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test we handle various errors in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_airobot_config_flow_client.get_settings.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    mock_airobot_config_flow_client.get_settings.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"] == TEST_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unique_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
) -> None:
    """Test we handle unique ID properly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

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


async def test_form_fallback_title(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
) -> None:
    """Test fallback title when device_name and device_id are empty."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Create simple objects with no device_name and no device_id
    class EmptySettings:
        device_name = None
        device_id = None

    class EmptyStatus:
        device_id = None

    mock_airobot_config_flow_client.get_statuses.return_value = EmptyStatus()
    mock_airobot_config_flow_client.get_settings.return_value = EmptySettings()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airobot TE1 192.168.1.100"
    assert result["data"] == TEST_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
) -> None:
    """Test DHCP discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="b8d61aabcdef",
            hostname="airobot-thermostat-te1",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"
    assert result["description_placeholders"] == {"host": "192.168.1.100"}

    # Complete the flow by providing credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "T01XXXXXX", CONF_PASSWORD: "test-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_USERNAME] == "T01XXXXXX"
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert "mac" in result["data"]


async def test_dhcp_discovery_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
) -> None:
    """Test DHCP discovery with error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="aabbccddeeff",
            hostname="airobot",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    # Test invalid auth
    mock_airobot_config_flow_client.get_statuses.side_effect = AirobotAuthError(
        "Invalid credentials"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "T01XXXXXX", CONF_PASSWORD: "wrong"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Test connection error
    mock_airobot_config_flow_client.get_statuses.side_effect = AirobotConnectionError(
        "Connection failed"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "T01XXXXXX", CONF_PASSWORD: "wrong"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Test unknown error
    mock_airobot_config_flow_client.get_statuses.side_effect = Exception(
        "Unknown error"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "T01XXXXXX", CONF_PASSWORD: "wrong"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_dhcp_discovery_duplicate(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
) -> None:
    """Test DHCP discovery with duplicate device."""
    # Create an existing entry via DHCP first
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="b8d61aabcdef",
            hostname="airobot-thermostat-te1",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    # Complete the setup
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "T01XXXXXX", CONF_PASSWORD: "test-password"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # DHCP discovers the same device again with potentially different IP
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.101",  # Different IP
            macaddress="b8d61aabcdef",  # Same MAC
            hostname="airobot-thermostat-te1",  # Same hostname = same device_id
        ),
    )
    await hass.async_block_till_done()

    # Should abort immediately since device_id extracted from hostname matches existing entry
    # and update the IP address
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the IP was updated in the existing entry
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == "192.168.1.101"


async def test_dhcp_discovery_non_standard_hostname(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_config_flow_client: AsyncMock,
) -> None:
    """Test DHCP discovery with non-standard hostname (device_id extracted from API)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="b8d61aabcdef",
            hostname="custom-hostname",  # Non-standard hostname
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    # Complete the setup - device_id will be obtained from API response
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "T01XXXXXX", CONF_PASSWORD: "test-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"  # From mock device_name
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "T01XXXXXX",
        CONF_PASSWORD: "test-password",
        CONF_MAC: "b8d61aabcdef",
    }

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == "T01XXXXXX"
