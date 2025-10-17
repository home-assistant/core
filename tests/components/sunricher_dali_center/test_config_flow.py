"""Test the DALI Center config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from PySrDaliGateway.exceptions import DaliGatewayError
import voluptuous as vol

from homeassistant.components.sunricher_dali_center.const import CONF_SN, DOMAIN
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
from homeassistant.helpers import selector

from tests.common import MockConfigEntry

_GATEWAY_DEFAULTS: dict[str, Any] = {
    "gw_sn": "6A242121110E",
    "gw_ip": "192.168.1.100",
    "port": 1883,
    "name": "Test Gateway",
    "username": "gateway_user",
    "passwd": "gateway_pass",
}


def _mock_gateway(**overrides: Any) -> MagicMock:
    """Create a mocked gateway with the expected interface."""
    info = _GATEWAY_DEFAULTS | overrides
    gateway = MagicMock()
    gateway.gw_sn = info["gw_sn"]
    gateway.gw_ip = info["gw_ip"]
    gateway.port = info["port"]
    gateway.name = info["name"]
    gateway.username = info["username"]
    gateway.passwd = info["passwd"]
    gateway.connect = AsyncMock()
    gateway.disconnect = AsyncMock()
    return gateway


async def test_discovery_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_discovery: MagicMock,
) -> None:
    """Test a successful discovery flow."""
    gateway = _mock_gateway()
    mock_discovery.discover_gateways.return_value = [gateway]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    schema = result["data_schema"].schema
    selector_field = schema["selected_gateway"]
    assert isinstance(selector_field, selector.SelectSelector)
    assert selector_field.config["options"] == [
        selector.SelectOptionDict(
            label=f"{gateway.name} ({gateway.gw_sn}, {gateway.gw_ip})",
            value=gateway.gw_sn,
        )
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == gateway.name
    assert result.get("data") == {
        CONF_SN: gateway.gw_sn,
        CONF_HOST: gateway.gw_ip,
        CONF_PORT: gateway.port,
        CONF_NAME: gateway.name,
        CONF_USERNAME: gateway.username,
        CONF_PASSWORD: gateway.passwd,
    }
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == gateway.gw_sn
    assert mock_discovery.discover_gateways.await_count == 1
    mock_setup_entry.assert_called_once()
    assert gateway.connect.await_count == 1
    assert gateway.disconnect.await_count == 1


async def test_discovery_no_gateways_found(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
) -> None:
    """Test discovery step when no gateways are found."""
    mock_discovery.discover_gateways.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    assert mock_discovery.discover_gateways.await_count == 1
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "no_devices_found"

    mock_discovery.discover_gateways.return_value = [_mock_gateway()]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    assert mock_discovery.discover_gateways.await_count == 2


async def test_discovery_gateway_error(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
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
    assert mock_discovery.discover_gateways.await_count == 1

    mock_discovery.discover_gateways.side_effect = None
    mock_discovery.discover_gateways.return_value = [_mock_gateway()]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    assert mock_discovery.discover_gateways.await_count == 2


async def test_discovery_device_not_found(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
) -> None:
    """Test selection error when the gateway no longer exists."""
    gateway = _mock_gateway()
    mock_discovery.discover_gateways.return_value = [gateway]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {})

    flow = hass.config_entries.flow._progress[flow_id]
    flow.data_schema = vol.Schema({vol.Optional("selected_gateway"): str})
    flow._discovered_gateways.clear()

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"selected_gateway": gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "device_not_found"
    assert mock_discovery.discover_gateways.await_count == 2

    mock_discovery.discover_gateways.return_value = [gateway]
    result = await hass.config_entries.flow.async_configure(flow_id, {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"


async def test_discovery_connection_failure(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
) -> None:
    """Test connection failure when validating the selected gateway."""
    gateway = _mock_gateway()
    mock_discovery.discover_gateways.return_value = [gateway]
    gateway.connect.side_effect = DaliGatewayError("failure")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "cannot_connect"
    assert gateway.connect.await_count == 1
    assert gateway.disconnect.await_count == 0

    gateway.connect.side_effect = None
    gateway.connect.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_duplicate_filtered(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that already configured gateways are filtered out."""
    gateway = _mock_gateway()

    mock_config_entry.add_to_hass(hass)

    mock_discovery.discover_gateways.return_value = [gateway]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "no_devices_found"
    assert mock_discovery.discover_gateways.await_count == 1

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"


async def test_discovery_unique_id_already_configured(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate protection when the entry appears during the flow."""
    gateway = _mock_gateway()
    mock_discovery.discover_gateways.return_value = [gateway]

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
        {"selected_gateway": gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_discovery.discover_gateways.await_count == 1
