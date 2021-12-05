"""Test the KNX config flow."""
from unittest.mock import patch

from xknx import XKNX
from xknx.io import DEFAULT_MCAST_GRP
from xknx.io.gateway_scanner import GatewayDescriptor

from homeassistant import config_entries
from homeassistant.components.knx import ConnectionSchema
from homeassistant.components.knx.config_flow import (
    CONF_KNX_GATEWAY,
    DEFAULT_ENTRY_DATA,
)
from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_ROUTING,
    CONF_KNX_TUNNELING,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry


def _gateway_descriptor(ip: str, port: int) -> GatewayDescriptor:
    """Get mock gw descriptor."""
    return GatewayDescriptor("Test", ip, port, "eth0", "127.0.0.1", True)


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
                ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
                CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
            },
        )
        await hass.async_block_till_done()
        assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result3["title"] == CONF_KNX_ROUTING.capitalize()
        assert result3["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "1.1.110",
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_tunneling_setup(hass: HomeAssistant) -> None:
    """Test tunneling if only one gateway is found."""
    gateway = _gateway_descriptor("192.168.0.1", 3675)
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
            {
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 3675,
            },
        )
        await hass.async_block_till_done()
        assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result3["title"] == "Tunneling @ 192.168.0.1"
        assert result3["data"] == {
            **DEFAULT_ENTRY_DATA,
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            ConnectionSchema.CONF_KNX_ROUTE_BACK: False,
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
            ConnectionSchema.CONF_KNX_ROUTE_BACK: False,
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


##
# Import Tests
##
async def test_import_config_tunneling(hass: HomeAssistant) -> None:
    """Test tunneling import from config.yaml."""
    config = {
        CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,
        ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,  # has a default in the original config
        ConnectionSchema.CONF_KNX_RATE_LIMIT: 20,  # has a default in the original config
        ConnectionSchema.CONF_KNX_STATE_UPDATER: True,  # has a default in the original config
        CONF_KNX_TUNNELING: {
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 3675,
            ConnectionSchema.CONF_KNX_ROUTE_BACK: True,
        },
    }

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Tunneling @ 192.168.1.1"
        assert result["data"] == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 3675,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            ConnectionSchema.CONF_KNX_ROUTE_BACK: True,
            ConnectionSchema.CONF_KNX_STATE_UPDATER: True,
            ConnectionSchema.CONF_KNX_RATE_LIMIT: 20,
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_import_config_routing(hass: HomeAssistant) -> None:
    """Test routing import from config.yaml."""
    config = {
        CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,  # has a default in the original config
        ConnectionSchema.CONF_KNX_RATE_LIMIT: 20,  # has a default in the original config
        ConnectionSchema.CONF_KNX_STATE_UPDATER: True,  # has a default in the original config
        CONF_KNX_ROUTING: {},  # is required when using routing
    }

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONF_KNX_ROUTING.capitalize()
        assert result["data"] == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            ConnectionSchema.CONF_KNX_STATE_UPDATER: True,
            ConnectionSchema.CONF_KNX_RATE_LIMIT: 20,
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_import_config_automatic(hass: HomeAssistant) -> None:
    """Test automatic import from config.yaml."""
    config = {
        CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,  # has a default in the original config
        ConnectionSchema.CONF_KNX_RATE_LIMIT: 20,  # has a default in the original config
        ConnectionSchema.CONF_KNX_STATE_UPDATER: True,  # has a default in the original config
    }

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONF_KNX_AUTOMATIC.capitalize()
        assert result["data"] == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            ConnectionSchema.CONF_KNX_STATE_UPDATER: True,
            ConnectionSchema.CONF_KNX_RATE_LIMIT: 20,
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_import_rate_limit_out_of_range(hass: HomeAssistant) -> None:
    """Test automatic import from config.yaml."""
    config = {
        CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,  # has a default in the original config
        ConnectionSchema.CONF_KNX_RATE_LIMIT: 80,
        ConnectionSchema.CONF_KNX_STATE_UPDATER: True,  # has a default in the original config
    }

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONF_KNX_AUTOMATIC.capitalize()
        assert result["data"] == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            ConnectionSchema.CONF_KNX_STATE_UPDATER: True,
            ConnectionSchema.CONF_KNX_RATE_LIMIT: 60,
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_import_options(hass: HomeAssistant) -> None:
    """Test import from config.yaml with options."""
    config = {
        CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,  # has a default in the original config
        ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,  # has a default in the original config
        ConnectionSchema.CONF_KNX_STATE_UPDATER: False,
        ConnectionSchema.CONF_KNX_RATE_LIMIT: 30,
    }

    with patch(
        "homeassistant.components.knx.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
        )
        await hass.async_block_till_done()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONF_KNX_AUTOMATIC.capitalize()
        assert result["data"] == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            ConnectionSchema.CONF_KNX_STATE_UPDATER: False,
            ConnectionSchema.CONF_KNX_RATE_LIMIT: 30,
        }

        assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_entry_exists_already(hass: HomeAssistant) -> None:
    """Test routing import from config.yaml."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


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
                ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
                ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            },
        )

        await hass.async_block_till_done()
        assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert not result2.get("data")

        assert mock_config_entry.data == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.255",
            CONF_HOST: "",
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            ConnectionSchema.CONF_KNX_RATE_LIMIT: 20,
            ConnectionSchema.CONF_KNX_STATE_UPDATER: True,
        }


async def test_tunneling_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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
                ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
                ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            },
        )

        assert result2.get("type") == RESULT_TYPE_FORM
        assert not result2.get("data")
        assert "flow_id" in result2

        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.1",
                CONF_PORT: 3675,
                ConnectionSchema.CONF_KNX_ROUTE_BACK: True,
            },
        )

        await hass.async_block_till_done()
        assert result3.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert not result3.get("data")

        assert mock_config_entry.data == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.255",
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            ConnectionSchema.CONF_KNX_RATE_LIMIT: 20,
            ConnectionSchema.CONF_KNX_STATE_UPDATER: True,
            CONF_HOST: "192.168.1.1",
            CONF_PORT: 3675,
            ConnectionSchema.CONF_KNX_ROUTE_BACK: True,
        }


async def test_advanced_options(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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
            user_input={
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
                CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
                ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
                ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                ConnectionSchema.CONF_KNX_RATE_LIMIT: 25,
                ConnectionSchema.CONF_KNX_STATE_UPDATER: False,
            },
        )

        await hass.async_block_till_done()
        assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert not result2.get("data")

        assert mock_config_entry.data == {
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_INDIVIDUAL_ADDRESS: "15.15.250",
            CONF_HOST: "",
            ConnectionSchema.CONF_KNX_MCAST_PORT: 3675,
            ConnectionSchema.CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            ConnectionSchema.CONF_KNX_RATE_LIMIT: 25,
            ConnectionSchema.CONF_KNX_STATE_UPDATER: False,
        }
