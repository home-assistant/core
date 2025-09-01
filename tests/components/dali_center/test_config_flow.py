"""Test the Dali Center config flow."""

from unittest.mock import AsyncMock, patch

from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant import config_entries
from homeassistant.components.dali_center.config_flow import CannotConnect
from homeassistant.components.dali_center.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_GATEWAY_DATA = {
    "gw_sn": "TEST123",
    "gw_ip": "192.168.1.100",
}


async def test_user_step_form(hass: HomeAssistant) -> None:
    """Test user step shows form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_discovery_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful discovery and configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # User confirms to start discovery
    with patch(
        "homeassistant.components.dali_center.config_flow.DaliGatewayDiscovery.discover_gateways",
        return_value=[MOCK_GATEWAY_DATA],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"

    # Mock gateway connection and validation
    with patch(
        "homeassistant.components.dali_center.config_flow.validate_input",
        return_value={"title": "Test Gateway", "gateway_info": MOCK_GATEWAY_DATA},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_gateway": MOCK_GATEWAY_DATA["gw_sn"]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Gateway"
    assert result["data"]["sn"] == MOCK_GATEWAY_DATA["gw_sn"]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_no_gateways_found(hass: HomeAssistant) -> None:
    """Test discovery when no gateways are found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dali_center.config_flow.DaliGatewayDiscovery.discover_gateways",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"
    assert result["errors"]["base"] == "no_devices_found"


async def test_discovery_gateway_connection_error(hass: HomeAssistant) -> None:
    """Test discovery with gateway connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dali_center.config_flow.DaliGatewayDiscovery.discover_gateways",
        return_value=[MOCK_GATEWAY_DATA],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Mock gateway connection failure
    with patch(
        "homeassistant.components.dali_center.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_gateway": MOCK_GATEWAY_DATA["gw_sn"]},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"
    assert result["errors"]["base"] == "cannot_connect"


async def test_discovery_exception(hass: HomeAssistant) -> None:
    """Test discovery with exception during gateway search."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dali_center.config_flow.DaliGatewayDiscovery.discover_gateways",
        side_effect=DaliGatewayError("Discovery failed"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"
    assert result["errors"]["base"] == "discovery_failed"


async def test_duplicate_prevention(hass: HomeAssistant) -> None:
    """Test that duplicate gateways are prevented."""
    # Create a mock existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"sn": MOCK_GATEWAY_DATA["gw_sn"]},
        unique_id=MOCK_GATEWAY_DATA["gw_sn"],
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.dali_center.config_flow.DaliGatewayDiscovery.discover_gateways",
            return_value=[MOCK_GATEWAY_DATA],
        ),
        patch(
            "homeassistant.components.dali_center.config_flow.validate_input",
            return_value={"title": "Test Gateway", "gateway_info": MOCK_GATEWAY_DATA},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_gateway": MOCK_GATEWAY_DATA["gw_sn"]},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
