"""Test the DHCP discovery integration."""
from unittest.mock import patch

from scapy.layers.l2 import Ether

from homeassistant.components import dhcp

from tests.common import mock_coro

# connect b8:b7:f1:6d:b5:33 192.168.210.56
RAW_DHCP_REQUEST = (
    b"\xff\xff\xff\xff\xff\xff\xb8\xb7\xf1m\xb53\x08\x00E\x00\x01P\x06E"
    b"\x00\x00\xff\x11\xb4X\x00\x00\x00\x00\xff\xff\xff\xff\x00D\x00C\x01<"
    b"\x0b\x14\x01\x01\x06\x00jmjV\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb8\xb7\xf1m\xb53\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00c\x82Sc5\x01\x039\x02\x05\xdc2\x04\xc0\xa8\xd286"
    b"\x04\xc0\xa8\xd0\x017\x04\x01\x03\x1c\x06\x0c\x07connect\xff\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
)


async def test_dhcp_match_hostname_and_macaddress(hass):
    """Test matching based on hostname and macaddress."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass,
        [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "dhcp"}
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_dhcp_match_hostname(hass):
    """Test matching based on hostname only."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, [{"domain": "mock-domain", "hostname": "connect"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "dhcp"}
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_dhcp_match_macaddress(hass):
    """Test matching based on macaddress only."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, [{"domain": "mock-domain", "macaddress": "B8B7F1*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "dhcp"}
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_dhcp_nomatch(hass):
    """Test not matching based on macaddress only."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, [{"domain": "mock-domain", "macaddress": "ABC123*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_dhcp_nomatch_hostname(hass):
    """Test not matching based on hostname only."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0
