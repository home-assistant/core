"""Test the Sunricher DALI config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.components.sunricher_dali.config_flow import OptionsFlowHandler
from homeassistant.components.sunricher_dali.const import CONF_SERIAL_NUMBER, DOMAIN
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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_options_flow_init(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow init step."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_refresh_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
) -> None:
    """Test gateway not found during refresh."""
    mock_config_entry.add_to_hass(hass)
    mock_discovery.discover_gateways.return_value = []

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"refresh": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "refresh"
    assert result["errors"]["base"] == "gateway_not_found"


async def test_options_flow_refresh_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
) -> None:
    """Test refresh with exception."""
    mock_config_entry.add_to_hass(hass)
    mock_discovery.discover_gateways.side_effect = DaliGatewayError("failure")

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"refresh": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "refresh"
    assert result["errors"]["base"] == "cannot_connect"


async def test_options_flow_refresh_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test successful gateway refresh with full flow."""

    mock_config_entry.add_to_hass(hass)
    mock_gateway.gw_ip = "192.168.1.101"
    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "refresh_result"
        assert result["description_placeholders"] == {
            "gateway_sn": mock_config_entry.data[CONF_SERIAL_NUMBER],
            "new_ip": "192.168.1.101",
        }
        assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"
        mock_reload.assert_awaited_once_with(mock_config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_refresh_reload_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test refresh when reload fails."""

    mock_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=False)
    ):
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "refresh"
        assert result["errors"]["base"] == "cannot_connect"


async def test_options_flow_refresh_with_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test refresh when config entry has runtime_data."""

    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = SimpleNamespace(gateway=mock_gateway)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ):
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        assert result["type"] is FlowResultType.FORM
        mock_gateway.disconnect.assert_awaited_once()


async def test_options_flow_refresh_result_creates_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test refresh_result step completes the options flow."""

    mock_config_entry.add_to_hass(hass)
    flow_handler = OptionsFlowHandler(mock_config_entry)
    flow_handler.hass = hass

    result = await flow_handler.async_step_refresh_result(user_input=None)

    assert result["type"] is FlowResultType.CREATE_ENTRY
