"""Test the DALI Center config flow."""

from unittest.mock import AsyncMock, MagicMock

from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.components.sunricher_dali_center.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_discovery_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test a successful discovery flow."""
    mock_discovery.discover_gateways.return_value = [mock_gateway]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == mock_gateway.name
    assert result.get("data") == {
        CONF_SERIAL_NUMBER: mock_gateway.gw_sn,
        CONF_HOST: mock_gateway.gw_ip,
        CONF_PORT: mock_gateway.port,
        CONF_NAME: mock_gateway.name,
        CONF_USERNAME: mock_gateway.username,
        CONF_PASSWORD: mock_gateway.passwd,
    }
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == mock_gateway.gw_sn
    mock_setup_entry.assert_called_once()
    mock_gateway.connect.assert_awaited_once()
    mock_gateway.disconnect.assert_awaited_once()


async def test_discovery_no_gateways_found(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test discovery step when no gateways are found."""
    mock_discovery.discover_gateways.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "no_devices_found"

    mock_discovery.discover_gateways.return_value = [mock_gateway]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_gateway_error(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test discovery error handling when gateway search fails."""
    mock_discovery.discover_gateways.side_effect = DaliGatewayError("failure")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "discovery_failed"

    mock_discovery.discover_gateways.side_effect = None
    mock_discovery.discover_gateways.return_value = [mock_gateway]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_connection_failure(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test connection failure when validating the selected gateway."""
    mock_discovery.discover_gateways.return_value = [mock_gateway]
    mock_gateway.connect.side_effect = DaliGatewayError("failure")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "cannot_connect"
    mock_gateway.connect.assert_awaited_once()
    mock_gateway.disconnect.assert_not_awaited()

    mock_gateway.connect.side_effect = None
    mock_gateway.connect.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_duplicate_filtered(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test that already configured gateways are filtered out."""
    mock_config_entry.add_to_hass(hass)

    mock_discovery.discover_gateways.return_value = [mock_gateway]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "no_devices_found"

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_unique_id_already_configured(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test duplicate protection when the entry appears during the flow."""
    mock_discovery.discover_gateways.return_value = [mock_gateway]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    duplicate_entry = MockConfigEntry(
        domain=mock_config_entry.domain,
        data=dict(mock_config_entry.data),
        unique_id=mock_config_entry.unique_id,
    )
    duplicate_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
