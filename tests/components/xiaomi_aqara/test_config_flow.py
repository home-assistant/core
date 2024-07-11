"""Test the Xiaomi Aqara config flow."""

from ipaddress import ip_address
from socket import gaierror
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.xiaomi_aqara import config_flow, const
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

ZEROCONF_NAME = "name"
ZEROCONF_PROP = "properties"
ZEROCONF_MAC = "mac"

TEST_HOST = "1.2.3.4"
TEST_HOST_2 = "5.6.7.8"
TEST_KEY = "1234567890123456"
TEST_PORT = 1234
TEST_NAME = "Test_Aqara_Gateway"
TEST_SID = "abcdefghijkl"
TEST_PROTOCOL = "1.1.1"
TEST_MAC = "ab:cd:ef:gh:ij:kl"
TEST_GATEWAY_ID = TEST_MAC
TEST_ZEROCONF_NAME = "lumi-gateway-v3_miio12345678._miio._udp.local."


@pytest.fixture(name="xiaomi_aqara", autouse=True)
def xiaomi_aqara_fixture():
    """Mock xiaomi_aqara discovery and entry setup."""
    mock_gateway_discovery = get_mock_discovery([TEST_HOST])

    with (
        patch(
            "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGatewayDiscovery",
            return_value=mock_gateway_discovery,
        ),
        patch(
            "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGateway",
            return_value=mock_gateway_discovery.gateways[TEST_HOST],
        ),
        patch(
            "homeassistant.components.xiaomi_aqara.async_setup_entry", return_value=True
        ),
    ):
        yield


def get_mock_discovery(
    host_list,
    invalid_interface=False,
    invalid_key=False,
    invalid_host=False,
    invalid_mac=False,
):
    """Return a mock gateway info instance."""
    gateway_discovery = Mock()

    gateway_dict = {}
    for host in host_list:
        gateway = Mock()

        gateway.ip_adress = host
        gateway.port = TEST_PORT
        gateway.sid = TEST_SID
        gateway.proto = TEST_PROTOCOL
        gateway.connection_error = invalid_host
        gateway.mac_error = invalid_mac

        if invalid_key:
            gateway.write_to_hub = Mock(return_value=False)

        gateway_dict[host] = gateway

    gateway_discovery.gateways = gateway_dict

    if invalid_interface:
        gateway_discovery.discover_gateways = Mock(side_effect=gaierror)

    return gateway_discovery


async def test_config_flow_user_success(hass: HomeAssistant) -> None:
    """Test a successful config flow initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_KEY: TEST_KEY, CONF_NAME: TEST_NAME},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_MAC: TEST_MAC,
        const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE,
        CONF_PROTOCOL: TEST_PROTOCOL,
        const.CONF_KEY: TEST_KEY,
        const.CONF_SID: TEST_SID,
    }


async def test_config_flow_user_multiple_success(hass: HomeAssistant) -> None:
    """Test a successful config flow initialized by the user with multiple gateways discovered."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_gateway_discovery = get_mock_discovery([TEST_HOST, TEST_HOST_2])

    with patch(
        "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGatewayDiscovery",
        return_value=mock_gateway_discovery,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"select_ip": TEST_HOST_2},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_KEY: TEST_KEY, CONF_NAME: TEST_NAME},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST_2,
        CONF_PORT: TEST_PORT,
        CONF_MAC: TEST_MAC,
        const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE,
        CONF_PROTOCOL: TEST_PROTOCOL,
        const.CONF_KEY: TEST_KEY,
        const.CONF_SID: TEST_SID,
    }


async def test_config_flow_user_no_key_success(hass: HomeAssistant) -> None:
    """Test a successful config flow initialized by the user without a key."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: TEST_NAME},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_MAC: TEST_MAC,
        const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE,
        CONF_PROTOCOL: TEST_PROTOCOL,
        const.CONF_KEY: None,
        const.CONF_SID: TEST_SID,
    }


async def test_config_flow_user_host_mac_success(hass: HomeAssistant) -> None:
    """Test a successful config flow initialized by the user with a host and mac specified."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_gateway_discovery = get_mock_discovery([])

    with patch(
        "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGatewayDiscovery",
        return_value=mock_gateway_discovery,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE,
                CONF_HOST: TEST_HOST,
                CONF_MAC: TEST_MAC,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: TEST_NAME},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_MAC: TEST_MAC,
        const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE,
        CONF_PROTOCOL: TEST_PROTOCOL,
        const.CONF_KEY: None,
        const.CONF_SID: TEST_SID,
    }


async def test_config_flow_user_discovery_error(hass: HomeAssistant) -> None:
    """Test a failed config flow initialized by the user with no gateways discovered."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_gateway_discovery = get_mock_discovery([])

    with patch(
        "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGatewayDiscovery",
        return_value=mock_gateway_discovery,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "discovery_error"}


async def test_config_flow_user_invalid_interface(hass: HomeAssistant) -> None:
    """Test a failed config flow initialized by the user with an invalid interface."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_gateway_discovery = get_mock_discovery([], invalid_interface=True)

    with patch(
        "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGatewayDiscovery",
        return_value=mock_gateway_discovery,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {const.CONF_INTERFACE: "invalid_interface"}


async def test_config_flow_user_invalid_host(hass: HomeAssistant) -> None:
    """Test a failed config flow initialized by the user with an invalid host."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_gateway_discovery = get_mock_discovery([TEST_HOST], invalid_host=True)

    with patch(
        "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGateway",
        return_value=mock_gateway_discovery.gateways[TEST_HOST],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE,
                CONF_HOST: "0.0.0.0",
                CONF_MAC: TEST_MAC,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "invalid_host"}


async def test_config_flow_user_invalid_mac(hass: HomeAssistant) -> None:
    """Test a failed config flow initialized by the user with an invalid mac."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_gateway_discovery = get_mock_discovery([TEST_HOST], invalid_mac=True)

    with patch(
        "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGateway",
        return_value=mock_gateway_discovery.gateways[TEST_HOST],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE,
                CONF_HOST: TEST_HOST,
                CONF_MAC: "in:va:li:d0:0m:ac",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"mac": "invalid_mac"}


async def test_config_flow_user_invalid_key(hass: HomeAssistant) -> None:
    """Test a failed config flow initialized by the user with an invalid key."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_gateway_discovery = get_mock_discovery([TEST_HOST], invalid_key=True)

    with patch(
        "homeassistant.components.xiaomi_aqara.config_flow.XiaomiGatewayDiscovery",
        return_value=mock_gateway_discovery,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_KEY: TEST_KEY, CONF_NAME: TEST_NAME},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert result["errors"] == {const.CONF_KEY: "invalid_key"}


async def test_zeroconf_success(hass: HomeAssistant) -> None:
    """Test a successful zeroconf discovery of a xiaomi aqara gateway."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            hostname="mock_hostname",
            name=TEST_ZEROCONF_NAME,
            port=None,
            properties={ZEROCONF_MAC: TEST_MAC},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_KEY: TEST_KEY, CONF_NAME: TEST_NAME},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_MAC: TEST_MAC,
        const.CONF_INTERFACE: config_flow.DEFAULT_INTERFACE,
        CONF_PROTOCOL: TEST_PROTOCOL,
        const.CONF_KEY: TEST_KEY,
        const.CONF_SID: TEST_SID,
    }


async def test_zeroconf_missing_data(hass: HomeAssistant) -> None:
    """Test a failed zeroconf discovery because of missing data."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            hostname="mock_hostname",
            name=TEST_ZEROCONF_NAME,
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_xiaomi_aqara"


async def test_zeroconf_unknown_device(hass: HomeAssistant) -> None:
    """Test a failed zeroconf discovery because of a unknown device."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            hostname="mock_hostname",
            name="not-a-xiaomi-aqara-gateway",
            port=None,
            properties={ZEROCONF_MAC: TEST_MAC},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_xiaomi_aqara"
