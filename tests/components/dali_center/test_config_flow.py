"""Test the Dali Center config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from PySrDaliGateway.exceptions import DaliGatewayError
import pytest

from homeassistant import config_entries
from homeassistant.components.dali_center.config_flow import (
    CannotConnect,
    validate_input,
)
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
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_discovery: MagicMock,
    mock_validate_input: MagicMock,
    mock_dali_gateway_class: MagicMock,
) -> None:
    """Test successful discovery and configuration."""
    mock_discovery.discover_gateways.return_value = [MOCK_GATEWAY_DATA]
    mock_validate_input.return_value = {
        "title": "Test Gateway",
        "gateway_info": MOCK_GATEWAY_DATA,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": MOCK_GATEWAY_DATA["gw_sn"]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Gateway"
    assert result["data"]["sn"] == MOCK_GATEWAY_DATA["gw_sn"]


async def test_discovery_no_gateways_found(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
) -> None:
    """Test discovery when no gateways are found."""
    mock_discovery.discover_gateways.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"
    assert result["errors"]["base"] == "no_devices_found"


async def test_discovery_gateway_connection_error(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_validate_input: MagicMock,
) -> None:
    """Test discovery with gateway connection error."""
    mock_discovery.discover_gateways.return_value = [MOCK_GATEWAY_DATA]
    mock_validate_input.side_effect = CannotConnect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Mock gateway connection failure
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


async def test_duplicate_prevention(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_validate_input: MagicMock,
) -> None:
    """Test that duplicate gateways are prevented."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"sn": MOCK_GATEWAY_DATA["gw_sn"]},
        unique_id=MOCK_GATEWAY_DATA["gw_sn"],
    )
    existing_entry.add_to_hass(hass)

    mock_discovery.discover_gateways.return_value = [MOCK_GATEWAY_DATA]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"
    assert result["errors"]["base"] == "no_devices_found"


async def test_validate_input_success(
    hass: HomeAssistant,
    mock_dali_gateway_class: MagicMock,
) -> None:
    """Test validate_input function with successful connection."""

    mock_gateway = mock_dali_gateway_class.return_value
    mock_gateway.name = "Test Gateway"

    data = {"gateway": MOCK_GATEWAY_DATA}
    result = await validate_input(hass, data)

    assert result["title"] == "Test Gateway"
    assert result["gateway_info"] == MOCK_GATEWAY_DATA
    mock_gateway.connect.assert_called_once()
    mock_gateway.disconnect.assert_called_once()


async def test_validate_input_dali_gateway_error(
    hass: HomeAssistant,
    mock_dali_gateway_class: MagicMock,
) -> None:
    """Test validate_input function with DaliGatewayError."""

    mock_gateway = mock_dali_gateway_class.return_value
    mock_gateway.connect.side_effect = DaliGatewayError("Connection failed")

    data = {"gateway": MOCK_GATEWAY_DATA}

    with pytest.raises(CannotConnect):
        await validate_input(hass, data)


async def test_discovery_unexpected_exception(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_validate_input: MagicMock,
) -> None:
    """Test discovery step with unexpected exception during gateway selection."""
    mock_discovery.discover_gateways.return_value = [MOCK_GATEWAY_DATA]
    mock_validate_input.side_effect = ValueError("Unexpected error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": MOCK_GATEWAY_DATA["gw_sn"]},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"
    assert result["errors"]["base"] == "unknown"
