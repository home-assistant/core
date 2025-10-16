"""Test the DALI Center config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from PySrDaliGateway.exceptions import DaliGatewayError

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

from tests.common import MockConfigEntry

_GATEWAY_DEFAULTS: dict[str, Any] = {
    "gw_sn": "TEST123",
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
    mock_setup_entry,
    mock_discovery,
) -> None:
    """Test a successful discovery flow."""
    gateway = _mock_gateway()
    mock_discovery.discover_gateways.return_value = [gateway]

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert init_result["type"] is FlowResultType.FORM
    assert init_result["step_id"] == "user"

    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )
    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "select_gateway"

    select_result = await hass.config_entries.flow.async_configure(
        discovery_result["flow_id"],
        {"selected_gateway": gateway.gw_sn},
    )

    assert select_result["type"] is FlowResultType.CREATE_ENTRY
    assert select_result["title"] == gateway.name
    assert select_result["data"] == {
        CONF_SN: gateway.gw_sn,
        CONF_HOST: gateway.gw_ip,
        CONF_PORT: gateway.port,
        CONF_NAME: gateway.name,
        CONF_USERNAME: gateway.username,
        CONF_PASSWORD: gateway.passwd,
    }
    assert mock_discovery.discover_gateways.await_count == 1
    mock_setup_entry.assert_called_once()
    assert gateway.connect.await_count == 1
    assert gateway.disconnect.await_count == 1


async def test_discovery_no_gateways_found(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test discovery step when no gateways are found."""
    mock_discovery.discover_gateways.return_value = []

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "select_gateway"
    assert discovery_result["errors"]["base"] == "no_devices_found"
    assert mock_discovery.discover_gateways.await_count == 1


async def test_discovery_gateway_error(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test discovery error handling when gateway search fails."""
    mock_discovery.discover_gateways.side_effect = DaliGatewayError("failure")

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "select_gateway"
    assert discovery_result["errors"]["base"] == "discovery_failed"
    assert mock_discovery.discover_gateways.await_count == 1


async def test_discovery_device_not_found(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test selection error when the gateway no longer exists."""
    gateway = _mock_gateway()
    mock_discovery.discover_gateways.return_value = [gateway]

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = init_result["flow_id"]
    _ = await hass.config_entries.flow.async_configure(flow_id, {})

    flow = hass.config_entries.flow._progress[flow_id]
    flow._discovered_gateways.clear()

    select_result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"selected_gateway": gateway.gw_sn},
    )

    assert select_result["type"] is FlowResultType.FORM
    assert select_result["step_id"] == "select_gateway"
    assert select_result["errors"]["base"] == "device_not_found"
    assert mock_discovery.discover_gateways.await_count == 2


async def test_discovery_connection_failure(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test connection failure when validating the selected gateway."""
    gateway = _mock_gateway()
    mock_discovery.discover_gateways.return_value = [gateway]
    gateway.connect.side_effect = DaliGatewayError("failure")

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "select_gateway"

    select_result = await hass.config_entries.flow.async_configure(
        discovery_result["flow_id"],
        {"selected_gateway": gateway.gw_sn},
    )

    assert select_result["type"] is FlowResultType.FORM
    assert select_result["step_id"] == "select_gateway"
    assert select_result["errors"]["base"] == "cannot_connect"
    assert gateway.connect.await_count == 1
    assert gateway.disconnect.await_count == 0


async def test_discovery_duplicate_filtered(
    hass: HomeAssistant,
    mock_discovery,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that already configured gateways are filtered out."""
    gateway = _mock_gateway()

    mock_config_entry.data = {
        CONF_SN: gateway.gw_sn,
        CONF_HOST: gateway.gw_ip,
        CONF_PORT: gateway.port,
        CONF_NAME: gateway.name,
        CONF_USERNAME: gateway.username,
        CONF_PASSWORD: gateway.passwd,
    }
    mock_config_entry.unique_id = gateway.gw_sn
    mock_config_entry.add_to_hass(hass)

    mock_discovery.discover_gateways.return_value = [gateway]

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "select_gateway"
    assert discovery_result["errors"]["base"] == "no_devices_found"
    assert mock_discovery.discover_gateways.await_count == 1


async def test_discovery_unique_id_already_configured(
    hass: HomeAssistant,
    mock_discovery,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate protection when the entry appears during the flow."""
    gateway = _mock_gateway()
    mock_discovery.discover_gateways.return_value = [gateway]

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    duplicate_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SN: gateway.gw_sn,
            CONF_HOST: gateway.gw_ip,
            CONF_PORT: gateway.port,
            CONF_NAME: gateway.name,
            CONF_USERNAME: gateway.username,
            CONF_PASSWORD: gateway.passwd,
        },
        unique_id=gateway.gw_sn,
    )
    duplicate_entry.add_to_hass(hass)

    select_result = await hass.config_entries.flow.async_configure(
        discovery_result["flow_id"],
        {"selected_gateway": gateway.gw_sn},
    )

    assert select_result["type"] is FlowResultType.ABORT
    assert select_result["reason"] == "already_configured"
    assert mock_discovery.discover_gateways.await_count == 1
