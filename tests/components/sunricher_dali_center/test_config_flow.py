"""Test the DALI Center config flow."""

from typing import Any

from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant import config_entries
from homeassistant.components.sunricher_dali_center.const import (
    CONF_CHANNEL_TOTAL,
    CONF_SN,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_GATEWAY_DATA: dict[str, Any] = {
    "gw_sn": "TEST123",
    "gw_ip": "192.168.1.100",
    "port": 1883,
    "name": "Test Gateway",
    "username": "gateway_user",
    "passwd": "gateway_pass",
    "channel_total": [1, 2, 3],
    "is_tls": True,
}


async def test_user_step_form(hass: HomeAssistant) -> None:
    """Test the initial user step shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_discovery_flow_success(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_discovery,
) -> None:
    """Test a successful discovery flow."""
    mock_discovery.discover_gateways.return_value = [MOCK_GATEWAY_DATA]

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )
    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "discovery"

    select_result = await hass.config_entries.flow.async_configure(
        discovery_result["flow_id"],
        {"selected_gateway": MOCK_GATEWAY_DATA["gw_sn"]},
    )
    await hass.async_block_till_done()

    assert select_result["type"] is FlowResultType.CREATE_ENTRY
    assert select_result["title"] == MOCK_GATEWAY_DATA["name"]
    assert select_result["data"] == {
        CONF_SN: MOCK_GATEWAY_DATA["gw_sn"],
        CONF_HOST: MOCK_GATEWAY_DATA["gw_ip"],
        CONF_PORT: MOCK_GATEWAY_DATA["port"],
        CONF_NAME: MOCK_GATEWAY_DATA["name"],
        CONF_USERNAME: MOCK_GATEWAY_DATA["username"],
        CONF_PASSWORD: MOCK_GATEWAY_DATA["passwd"],
        CONF_CHANNEL_TOTAL: MOCK_GATEWAY_DATA["channel_total"],
        CONF_SSL: MOCK_GATEWAY_DATA["is_tls"],
    }
    assert mock_discovery.discover_gateways.await_count == 1
    mock_setup_entry.assert_called_once()


async def test_discovery_no_gateways_found(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test discovery step when no gateways are found."""
    mock_discovery.discover_gateways.return_value = []

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "discovery"
    assert discovery_result["errors"]["base"] == "no_devices_found"
    assert mock_discovery.discover_gateways.await_count == 1


async def test_discovery_gateway_error(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test discovery error handling when gateway search fails."""
    mock_discovery.discover_gateways.side_effect = DaliGatewayError("failure")

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "discovery"
    assert discovery_result["errors"]["base"] == "discovery_failed"
    assert mock_discovery.discover_gateways.await_count == 1


async def test_discovery_device_not_found(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test selection error when the gateway no longer exists."""
    mock_discovery.discover_gateways.return_value = [MOCK_GATEWAY_DATA]

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow_id = init_result["flow_id"]
    _ = await hass.config_entries.flow.async_configure(flow_id, {})

    flow = hass.config_entries.flow._progress[flow_id]
    flow._discovered_gateways.clear()

    select_result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"selected_gateway": MOCK_GATEWAY_DATA["gw_sn"]},
    )

    assert select_result["type"] is FlowResultType.FORM
    assert select_result["step_id"] == "discovery"
    assert select_result["errors"]["base"] == "device_not_found"
    assert mock_discovery.discover_gateways.await_count == 2


async def test_discovery_duplicate_filtered(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test that already configured gateways are filtered out."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SN: MOCK_GATEWAY_DATA["gw_sn"],
            CONF_HOST: MOCK_GATEWAY_DATA["gw_ip"],
            CONF_PORT: MOCK_GATEWAY_DATA["port"],
            CONF_NAME: MOCK_GATEWAY_DATA["name"],
            CONF_USERNAME: MOCK_GATEWAY_DATA["username"],
            CONF_PASSWORD: MOCK_GATEWAY_DATA["passwd"],
            CONF_CHANNEL_TOTAL: MOCK_GATEWAY_DATA["channel_total"],
            CONF_SSL: MOCK_GATEWAY_DATA["is_tls"],
        },
        unique_id=MOCK_GATEWAY_DATA["gw_sn"],
    )
    existing_entry.add_to_hass(hass)

    mock_discovery.discover_gateways.return_value = [MOCK_GATEWAY_DATA]

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "discovery"
    assert discovery_result["errors"]["base"] == "no_devices_found"
    assert mock_discovery.discover_gateways.await_count == 1


async def test_discovery_unique_id_already_configured(
    hass: HomeAssistant,
    mock_discovery,
) -> None:
    """Test duplicate protection when the entry appears during the flow."""
    mock_discovery.discover_gateways.return_value = [MOCK_GATEWAY_DATA]

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    discovery_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], {}
    )

    duplicate_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SN: MOCK_GATEWAY_DATA["gw_sn"],
            CONF_HOST: MOCK_GATEWAY_DATA["gw_ip"],
            CONF_PORT: MOCK_GATEWAY_DATA["port"],
            CONF_NAME: MOCK_GATEWAY_DATA["name"],
            CONF_USERNAME: MOCK_GATEWAY_DATA["username"],
            CONF_PASSWORD: MOCK_GATEWAY_DATA["passwd"],
            CONF_CHANNEL_TOTAL: MOCK_GATEWAY_DATA["channel_total"],
            CONF_SSL: MOCK_GATEWAY_DATA["is_tls"],
        },
        unique_id=MOCK_GATEWAY_DATA["gw_sn"],
    )
    duplicate_entry.add_to_hass(hass)

    select_result = await hass.config_entries.flow.async_configure(
        discovery_result["flow_id"],
        {"selected_gateway": MOCK_GATEWAY_DATA["gw_sn"]},
    )

    assert select_result["type"] is FlowResultType.ABORT
    assert select_result["reason"] == "already_configured"
    assert mock_discovery.discover_gateways.await_count == 1
