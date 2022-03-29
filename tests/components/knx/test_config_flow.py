"""Test the KNX config flow."""
from unittest.mock import patch

import pytest
from xknx.io import DEFAULT_MCAST_GRP
from xknx.io.gateway_scanner import GatewayDescriptor

from homeassistant import config_entries
from homeassistant.components.knx.config_flow import (
    CONF_DEFAULT_LOCAL_IP,
    CONF_KNX_GATEWAY,
    CONF_KNX_LABEL_TUNNELING_TCP,
    CONF_KNX_LABEL_TUNNELING_UDP,
    CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK,
    CONF_KNX_TUNNELING_TYPE,
    DEFAULT_ENTRY_DATA,
    get_knx_tunneling_type,
)
from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_LOCAL_IP,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_ROUTE_BACK,
    CONF_KNX_ROUTING,
    CONF_KNX_STATE_UPDATER,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry


def _gateway_descriptor(
    ip: str, port: int, supports_tunnelling_tcp: bool = False
) -> GatewayDescriptor:
    """Get mock gw descriptor."""
    return GatewayDescriptor(
        name="Test",
        ip_addr=ip,
        port=port,
        local_interface="eth0",
        local_ip="127.0.0.1",
        supports_routing=True,
        supports_tunnelling=True,
        supports_tunnelling_tcp=supports_tunnelling_tcp,
    )


async def test_user_single_instance(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_routing_setup(hass: HomeAssistant) -> None:
    """Test routing setup."""
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = []
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "routing"
    assert not result2["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
            },
        )
        await hass.async_block_till_done()
        assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result3["title"] == CONF_KNX_ROUTING.capitalize()
        assert result3["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_LOCAL_IP: None,
            CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_routing_setup_advanced(hass: HomeAssistant) -> None:
    """Test routing setup with advanced options."""
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = []
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_USER,
                "show_advanced_options": True,
            },
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "routing"
    assert not result2["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
                CONF_KNX_LOCAL_IP: "192.168.1.112",
            },
        )
        await hass.async_block_till_done()
        assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result3["title"] == CONF_KNX_ROUTING.capitalize()
        assert result3["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_LOCAL_IP: "192.168.1.112",
            CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
        }

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "user_input,config_entry_data",
    [
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_LABEL_TUNNELING_UDP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
            },
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
                CONF_KNX_ROUTE_BACK: False,
                CONF_KNX_LOCAL_IP: None,
            },
        ),
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_LABEL_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
            },
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
                CONF_KNX_ROUTE_BACK: False,
                CONF_KNX_LOCAL_IP: None,
            },
        ),
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
            },
            {
                **DEFAULT_ENTRY_DATA,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
                CONF_KNX_ROUTE_BACK: True,
                CONF_KNX_LOCAL_IP: None,
            },
        ),
    ],
)
async def test_tunneling_setup(
    hass: HomeAssistant, user_input, config_entry_data
) -> None:
    """Test tunneling if only one gateway is found."""
    gateway = _gateway_descriptor("192.168.0.1", 3675, True)
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = [gateway]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "manual_tunnel"
    assert not result2["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input,
        )
        await hass.async_block_till_done()
        assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result3["title"] == "Tunneling @ 192.168.0.1"
        assert result3["data"] == config_entry_data

        assert len(mock_setup_entry.mock_calls) == 1


async def test_tunneling_setup_for_local_ip(hass: HomeAssistant) -> None:
    """Test tunneling if only one gateway is found."""
    gateway = _gateway_descriptor("192.168.0.2", 3675)
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = [gateway]
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_USER,
                "show_advanced_options": True,
            },
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "manual_tunnel"
    assert not result2["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_LABEL_TUNNELING_UDP,
                CONF_HOST: "192.168.0.2",
                CONF_PORT: 3675,
                CONF_KNX_LOCAL_IP: "192.168.1.112",
            },
        )
        await hass.async_block_till_done()
        assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result3["title"] == "Tunneling @ 192.168.0.2"
        assert result3["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.0.2",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_LOCAL_IP: "192.168.1.112",
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_tunneling_setup_for_multiple_found_gateways(hass: HomeAssistant) -> None:
    """Test tunneling if only one gateway is found."""
    gateway = _gateway_descriptor("192.168.0.1", 3675)
    gateway2 = _gateway_descriptor("192.168.1.100", 3675)
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = [gateway, gateway2]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert not result["errors"]

    tunnel_flow = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert tunnel_flow["type"] == RESULT_TYPE_FORM
    assert tunnel_flow["step_id"] == "tunnel"
    assert not tunnel_flow["errors"]

    manual_tunnel = await hass.config_entries.flow.async_configure(
        tunnel_flow["flow_id"],
        {CONF_KNX_GATEWAY: str(gateway)},
    )
    await hass.async_block_till_done()
    assert manual_tunnel["type"] == RESULT_TYPE_FORM
    assert manual_tunnel["step_id"] == "manual_tunnel"

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        manual_tunnel_flow = await hass.config_entries.flow.async_configure(
            manual_tunnel["flow_id"],
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_LABEL_TUNNELING_UDP,
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
            },
        )
        await hass.async_block_till_done()
        assert manual_tunnel_flow["type"] == RESULT_TYPE_CREATE_ENTRY
        assert manual_tunnel_flow["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            CONF_KNX_ROUTE_BACK: False,
            CONF_KNX_LOCAL_IP: None,
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_tunnel_step_when_no_gateway(hass: HomeAssistant) -> None:
    """Test manual tunnel if no gateway is found and tunneling is selected."""
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = []
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert not result["errors"]

    tunnel_flow = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
        },
    )
    await hass.async_block_till_done()
    assert tunnel_flow["type"] == RESULT_TYPE_FORM
    assert tunnel_flow["step_id"] == "manual_tunnel"
    assert not tunnel_flow["errors"]


async def test_form_with_automatic_connection_handling(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = [_gateway_descriptor("192.168.0.1", 3675)]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert not result["errors"]

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == CONF_KNX_AUTOMATIC.capitalize()
    assert result2["data"] == {
        **DEFAULT_ENTRY_DATA,
        CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options config flow."""
    mock_config_entry.add_to_hass(hass)

    gateway = _gateway_descriptor("192.168.0.1", 3675)
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = [gateway]
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        assert result.get("type") == RESULT_TYPE_FORM
        assert result.get("step_id") == "init"
        assert "flow_id" in result

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.255",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            },
        )

        await hass.async_block_till_done()
        assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert not result2.get("data")

        assert mock_config_entry.data == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.255",
            CONF_HOST: "",
            CONF_KNX_LOCAL_IP: None,
            CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_RATE_LIMIT: 20,
            CONF_KNX_STATE_UPDATER: True,
        }


@pytest.mark.parametrize(
    "user_input,config_entry_data",
    [
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK,
                CONF_HOST: "192.168.1.1",
                CONF_PORT: 3675,
            },
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.255",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_RATE_LIMIT: 20,
                CONF_KNX_STATE_UPDATER: True,
                CONF_KNX_LOCAL_IP: None,
                CONF_HOST: "192.168.1.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: True,
            },
        ),
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_LABEL_TUNNELING_UDP,
                CONF_HOST: "192.168.1.1",
                CONF_PORT: 3675,
            },
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.255",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_RATE_LIMIT: 20,
                CONF_KNX_STATE_UPDATER: True,
                CONF_KNX_LOCAL_IP: None,
                CONF_HOST: "192.168.1.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: False,
            },
        ),
        (
            {
                CONF_KNX_TUNNELING_TYPE: CONF_KNX_LABEL_TUNNELING_TCP,
                CONF_HOST: "192.168.1.1",
                CONF_PORT: 3675,
            },
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.255",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_RATE_LIMIT: 20,
                CONF_KNX_STATE_UPDATER: True,
                CONF_KNX_LOCAL_IP: None,
                CONF_HOST: "192.168.1.1",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: False,
            },
        ),
    ],
)
async def test_tunneling_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input,
    config_entry_data,
) -> None:
    """Test options flow for tunneling."""
    mock_config_entry.add_to_hass(hass)

    gateway = _gateway_descriptor("192.168.0.1", 3675)
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = [gateway]
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        assert result.get("type") == RESULT_TYPE_FORM
        assert result.get("step_id") == "init"
        assert "flow_id" in result

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.255",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            },
        )

        assert result2.get("type") == RESULT_TYPE_FORM
        assert not result2.get("data")
        assert "flow_id" in result2

        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input=user_input,
        )

        await hass.async_block_till_done()
        assert result3.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert not result3.get("data")

        assert mock_config_entry.data == config_entry_data


@pytest.mark.parametrize(
    "user_input,config_entry_data",
    [
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_RATE_LIMIT: 25,
                CONF_KNX_STATE_UPDATER: False,
                CONF_KNX_LOCAL_IP: "192.168.1.112",
            },
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
                CONF_HOST: "",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_RATE_LIMIT: 25,
                CONF_KNX_STATE_UPDATER: False,
                CONF_KNX_LOCAL_IP: "192.168.1.112",
            },
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_RATE_LIMIT: 25,
                CONF_KNX_STATE_UPDATER: False,
                CONF_KNX_LOCAL_IP: CONF_DEFAULT_LOCAL_IP,
            },
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
                CONF_HOST: "",
                CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_RATE_LIMIT: 25,
                CONF_KNX_STATE_UPDATER: False,
                CONF_KNX_LOCAL_IP: None,
            },
        ),
    ],
)
async def test_advanced_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input,
    config_entry_data,
) -> None:
    """Test options config flow."""
    mock_config_entry.add_to_hass(hass)

    gateway = _gateway_descriptor("192.168.0.1", 3675)
    with patch("xknx.io.gateway_scanner.GatewayScanner.scan") as gateways:
        gateways.return_value = [gateway]
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id, context={"show_advanced_options": True}
        )

        assert result.get("type") == RESULT_TYPE_FORM
        assert result.get("step_id") == "init"
        assert "flow_id" in result

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        await hass.async_block_till_done()
        assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert not result2.get("data")

        assert mock_config_entry.data == config_entry_data


@pytest.mark.parametrize(
    "config_entry_data,result",
    [
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_KNX_ROUTE_BACK: False,
            },
            CONF_KNX_LABEL_TUNNELING_UDP,
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_KNX_ROUTE_BACK: True,
            },
            CONF_KNX_LABEL_TUNNELING_UDP_ROUTE_BACK,
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_KNX_ROUTE_BACK: False,
            },
            CONF_KNX_LABEL_TUNNELING_TCP,
        ),
    ],
)
async def test_get_knx_tunneling_type(
    config_entry_data,
    result,
) -> None:
    """Test converting config entry data to tunneling type for config flow."""
    assert get_knx_tunneling_type(config_entry_data) == result
