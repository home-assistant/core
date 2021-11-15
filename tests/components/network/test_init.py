"""Test the Network Configuration."""
from ipaddress import IPv4Address
from unittest.mock import MagicMock, Mock, patch

import ifaddr

from homeassistant.components import network
from homeassistant.components.network.const import (
    ATTR_ADAPTERS,
    ATTR_CONFIGURED_ADAPTERS,
    DOMAIN,
    MDNS_TARGET_IP,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from homeassistant.setup import async_setup_component

_NO_LOOPBACK_IPADDR = "192.168.1.5"
_LOOPBACK_IPADDR = "127.0.0.1"


def _mock_socket(sockname):
    mock_socket = MagicMock()
    mock_socket.getsockname = Mock(return_value=sockname)
    return mock_socket


def _mock_socket_exception(exc):
    mock_socket = MagicMock()
    mock_socket.getsockname = Mock(side_effect=exc)
    return mock_socket


def _generate_mock_adapters():
    mock_lo0 = Mock(spec=ifaddr.Adapter)
    mock_lo0.nice_name = "lo0"
    mock_lo0.ips = [ifaddr.IP("127.0.0.1", 8, "lo0")]
    mock_lo0.index = 0
    mock_eth0 = Mock(spec=ifaddr.Adapter)
    mock_eth0.nice_name = "eth0"
    mock_eth0.ips = [ifaddr.IP(("2001:db8::", 1, 1), 8, "eth0")]
    mock_eth0.index = 1
    mock_eth1 = Mock(spec=ifaddr.Adapter)
    mock_eth1.nice_name = "eth1"
    mock_eth1.ips = [ifaddr.IP("192.168.1.5", 23, "eth1")]
    mock_eth1.index = 2
    mock_vtun0 = Mock(spec=ifaddr.Adapter)
    mock_vtun0.nice_name = "vtun0"
    mock_vtun0.ips = [ifaddr.IP("169.254.3.2", 16, "vtun0")]
    mock_vtun0.index = 3
    return [mock_eth0, mock_lo0, mock_eth1, mock_vtun0]


async def test_async_detect_interfaces_setting_non_loopback_route(hass, hass_storage):
    """Test without default interface config and the route returns a non-loopback address."""
    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket([_NO_LOOPBACK_IPADDR]),
    ), patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    network_obj = hass.data[DOMAIN]
    assert network_obj.configured_adapters == []

    assert network_obj.adapters == [
        {
            "auto": False,
            "index": 1,
            "default": False,
            "enabled": False,
            "ipv4": [],
            "ipv6": [
                {
                    "address": "2001:db8::",
                    "network_prefix": 8,
                    "flowinfo": 1,
                    "scope_id": 1,
                }
            ],
            "name": "eth0",
        },
        {
            "index": 0,
            "auto": False,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "127.0.0.1", "network_prefix": 8}],
            "ipv6": [],
            "name": "lo0",
        },
        {
            "index": 2,
            "auto": True,
            "default": True,
            "enabled": True,
            "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
            "ipv6": [],
            "name": "eth1",
        },
        {
            "index": 3,
            "auto": False,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
            "ipv6": [],
            "name": "vtun0",
        },
    ]


async def test_async_detect_interfaces_setting_loopback_route(hass, hass_storage):
    """Test without default interface config and the route returns a loopback address."""
    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket([_LOOPBACK_IPADDR]),
    ), patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    network_obj = hass.data[DOMAIN]
    assert network_obj.configured_adapters == []
    assert network_obj.adapters == [
        {
            "index": 1,
            "auto": True,
            "default": False,
            "enabled": True,
            "ipv4": [],
            "ipv6": [
                {
                    "address": "2001:db8::",
                    "network_prefix": 8,
                    "flowinfo": 1,
                    "scope_id": 1,
                }
            ],
            "name": "eth0",
        },
        {
            "index": 0,
            "auto": False,
            "default": True,
            "enabled": False,
            "ipv4": [{"address": "127.0.0.1", "network_prefix": 8}],
            "ipv6": [],
            "name": "lo0",
        },
        {
            "index": 2,
            "auto": True,
            "default": False,
            "enabled": True,
            "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
            "ipv6": [],
            "name": "eth1",
        },
        {
            "index": 3,
            "auto": False,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
            "ipv6": [],
            "name": "vtun0",
        },
    ]


async def test_async_detect_interfaces_setting_empty_route(hass, hass_storage):
    """Test without default interface config and the route returns nothing."""
    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket([]),
    ), patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    network_obj = hass.data[DOMAIN]
    assert network_obj.configured_adapters == []
    assert network_obj.adapters == [
        {
            "auto": True,
            "index": 1,
            "default": False,
            "enabled": True,
            "ipv4": [],
            "ipv6": [
                {
                    "address": "2001:db8::",
                    "network_prefix": 8,
                    "flowinfo": 1,
                    "scope_id": 1,
                }
            ],
            "name": "eth0",
        },
        {
            "auto": False,
            "index": 0,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "127.0.0.1", "network_prefix": 8}],
            "ipv6": [],
            "name": "lo0",
        },
        {
            "auto": True,
            "index": 2,
            "default": False,
            "enabled": True,
            "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
            "ipv6": [],
            "name": "eth1",
        },
        {
            "auto": False,
            "index": 3,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
            "ipv6": [],
            "name": "vtun0",
        },
    ]


async def test_async_detect_interfaces_setting_exception(hass, hass_storage):
    """Test without default interface config and the route throws an exception."""
    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket_exception(AttributeError),
    ), patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    network_obj = hass.data[DOMAIN]
    assert network_obj.configured_adapters == []
    assert network_obj.adapters == [
        {
            "auto": True,
            "index": 1,
            "default": False,
            "enabled": True,
            "ipv4": [],
            "ipv6": [
                {
                    "address": "2001:db8::",
                    "network_prefix": 8,
                    "flowinfo": 1,
                    "scope_id": 1,
                }
            ],
            "name": "eth0",
        },
        {
            "auto": False,
            "index": 0,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "127.0.0.1", "network_prefix": 8}],
            "ipv6": [],
            "name": "lo0",
        },
        {
            "auto": True,
            "index": 2,
            "default": False,
            "enabled": True,
            "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
            "ipv6": [],
            "name": "eth1",
        },
        {
            "auto": False,
            "index": 3,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
            "ipv6": [],
            "name": "vtun0",
        },
    ]


async def test_interfaces_configured_from_storage(hass, hass_storage):
    """Test settings from storage are preferred over auto configure."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {ATTR_CONFIGURED_ADAPTERS: ["eth0", "eth1", "vtun0"]},
    }
    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket([_NO_LOOPBACK_IPADDR]),
    ), patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    network_obj = hass.data[DOMAIN]
    assert network_obj.configured_adapters == ["eth0", "eth1", "vtun0"]

    assert network_obj.adapters == [
        {
            "auto": False,
            "index": 1,
            "default": False,
            "enabled": True,
            "ipv4": [],
            "ipv6": [
                {
                    "address": "2001:db8::",
                    "network_prefix": 8,
                    "flowinfo": 1,
                    "scope_id": 1,
                }
            ],
            "name": "eth0",
        },
        {
            "auto": False,
            "index": 0,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "127.0.0.1", "network_prefix": 8}],
            "ipv6": [],
            "name": "lo0",
        },
        {
            "auto": True,
            "index": 2,
            "default": True,
            "enabled": True,
            "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
            "ipv6": [],
            "name": "eth1",
        },
        {
            "auto": False,
            "index": 3,
            "default": False,
            "enabled": True,
            "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
            "ipv6": [],
            "name": "vtun0",
        },
    ]


async def test_interfaces_configured_from_storage_websocket_update(
    hass, hass_ws_client, hass_storage
):
    """Test settings from storage can be updated via websocket api."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {ATTR_CONFIGURED_ADAPTERS: ["eth0", "eth1", "vtun0"]},
    }
    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket([_NO_LOOPBACK_IPADDR]),
    ), patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    network_obj = hass.data[DOMAIN]
    assert network_obj.configured_adapters == ["eth0", "eth1", "vtun0"]
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({"id": 1, "type": "network"})

    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"][ATTR_CONFIGURED_ADAPTERS] == ["eth0", "eth1", "vtun0"]
    assert response["result"][ATTR_ADAPTERS] == [
        {
            "auto": False,
            "index": 1,
            "default": False,
            "enabled": True,
            "ipv4": [],
            "ipv6": [
                {
                    "address": "2001:db8::",
                    "network_prefix": 8,
                    "flowinfo": 1,
                    "scope_id": 1,
                }
            ],
            "name": "eth0",
        },
        {
            "auto": False,
            "index": 0,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "127.0.0.1", "network_prefix": 8}],
            "ipv6": [],
            "name": "lo0",
        },
        {
            "auto": True,
            "index": 2,
            "default": True,
            "enabled": True,
            "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
            "ipv6": [],
            "name": "eth1",
        },
        {
            "auto": False,
            "index": 3,
            "default": False,
            "enabled": True,
            "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
            "ipv6": [],
            "name": "vtun0",
        },
    ]

    await ws_client.send_json(
        {"id": 2, "type": "network/configure", "config": {ATTR_CONFIGURED_ADAPTERS: []}}
    )
    response = await ws_client.receive_json()
    assert response["result"][ATTR_CONFIGURED_ADAPTERS] == []

    await ws_client.send_json({"id": 3, "type": "network"})
    response = await ws_client.receive_json()
    assert response["result"][ATTR_CONFIGURED_ADAPTERS] == []
    assert response["result"][ATTR_ADAPTERS] == [
        {
            "auto": False,
            "index": 1,
            "default": False,
            "enabled": False,
            "ipv4": [],
            "ipv6": [
                {
                    "address": "2001:db8::",
                    "network_prefix": 8,
                    "flowinfo": 1,
                    "scope_id": 1,
                }
            ],
            "name": "eth0",
        },
        {
            "auto": False,
            "index": 0,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "127.0.0.1", "network_prefix": 8}],
            "ipv6": [],
            "name": "lo0",
        },
        {
            "auto": True,
            "index": 2,
            "default": True,
            "enabled": True,
            "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
            "ipv6": [],
            "name": "eth1",
        },
        {
            "auto": False,
            "index": 3,
            "default": False,
            "enabled": False,
            "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
            "ipv6": [],
            "name": "vtun0",
        },
    ]


async def test_async_get_source_ip_matching_interface(hass, hass_storage):
    """Test getting the source ip address with interface matching."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {ATTR_CONFIGURED_ADAPTERS: ["eth1"]},
    }

    with patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ), patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket(["192.168.1.5"]),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

        assert await network.async_get_source_ip(hass, MDNS_TARGET_IP) == "192.168.1.5"


async def test_async_get_source_ip_interface_not_match(hass, hass_storage):
    """Test getting the source ip address with interface does not match."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {ATTR_CONFIGURED_ADAPTERS: ["vtun0"]},
    }

    with patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ), patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket(["192.168.1.5"]),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

        assert await network.async_get_source_ip(hass, MDNS_TARGET_IP) == "169.254.3.2"


async def test_async_get_source_ip_cannot_determine_target(hass, hass_storage):
    """Test getting the source ip address when getsockname fails."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {ATTR_CONFIGURED_ADAPTERS: ["eth1"]},
    }

    with patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ), patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket([None]),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

        assert await network.async_get_source_ip(hass, MDNS_TARGET_IP) == "192.168.1.5"


async def test_async_get_ipv4_broadcast_addresses_default(hass, hass_storage):
    """Test getting ipv4 broadcast addresses when only the default address is enabled."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {ATTR_CONFIGURED_ADAPTERS: ["eth1"]},
    }

    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket(["192.168.1.5"]),
    ), patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    assert await network.async_get_ipv4_broadcast_addresses(hass) == {
        IPv4Address("255.255.255.255")
    }


async def test_async_get_ipv4_broadcast_addresses_multiple(hass, hass_storage):
    """Test getting ipv4 broadcast addresses when multiple adapters are enabled."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "key": STORAGE_KEY,
        "data": {ATTR_CONFIGURED_ADAPTERS: ["eth1", "vtun0"]},
    }

    with patch(
        "homeassistant.components.network.util.socket.socket",
        return_value=_mock_socket([_LOOPBACK_IPADDR]),
    ), patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=_generate_mock_adapters(),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    assert await network.async_get_ipv4_broadcast_addresses(hass) == {
        IPv4Address("255.255.255.255"),
        IPv4Address("192.168.1.255"),
        IPv4Address("169.254.255.255"),
    }
