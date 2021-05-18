"""Test the DHCP discovery integration."""
import datetime
import threading
from unittest.mock import patch

from scapy.error import Scapy_Exception
from scapy.layers.dhcp import DHCP
from scapy.layers.l2 import Ether

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.device_tracker.const import (
    ATTR_HOST_NAME,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

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

# iRobot-AE9EC12DD3B04885BCBFA36AFB01E1CC 50:14:79:03:85:2c 192.168.1.120
RAW_DHCP_RENEWAL = (
    b"\x00\x15\x5d\x8e\xed\x02\x50\x14\x79\x03\x85\x2c\x08\x00\x45\x00"
    b"\x01\x8e\x51\xd2\x40\x00\x40\x11\x63\xa1\xc0\xa8\x01\x78\xc0\xa8"
    b"\x01\x23\x00\x44\x00\x43\x01\x7a\x12\x09\x01\x01\x06\x00\xd4\xea"
    b"\xb2\xfd\xff\xff\x00\x00\xc0\xa8\x01\x78\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x50\x14\x79\x03\x85\x2c\x00\x00\x00\x00"
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
    b"\x00\x00\x00\x00\x00\x00\x63\x82\x53\x63\x35\x01\x03\x39\x02\x05"
    b"\xdc\x3c\x45\x64\x68\x63\x70\x63\x64\x2d\x35\x2e\x32\x2e\x31\x30"
    b"\x3a\x4c\x69\x6e\x75\x78\x2d\x33\x2e\x31\x38\x2e\x37\x31\x3a\x61"
    b"\x72\x6d\x76\x37\x6c\x3a\x51\x75\x61\x6c\x63\x6f\x6d\x6d\x20\x54"
    b"\x65\x63\x68\x6e\x6f\x6c\x6f\x67\x69\x65\x73\x2c\x20\x49\x6e\x63"
    b"\x20\x41\x50\x51\x38\x30\x30\x39\x0c\x27\x69\x52\x6f\x62\x6f\x74"
    b"\x2d\x41\x45\x39\x45\x43\x31\x32\x44\x44\x33\x42\x30\x34\x38\x38"
    b"\x35\x42\x43\x42\x46\x41\x33\x36\x41\x46\x42\x30\x31\x45\x31\x43"
    b"\x43\x37\x08\x01\x21\x03\x06\x1c\x33\x3a\x3b\xff"
)


async def test_dhcp_match_hostname_and_macaddress(hass):
    """Test matching based on hostname and macaddress."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass,
        {},
        [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)
        # Ensure no change is ignored
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_dhcp_renewal_match_hostname_and_macaddress(hass):
    """Test renewal matching based on hostname and macaddress."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass,
        {},
        [{"domain": "mock-domain", "hostname": "irobot-*", "macaddress": "501479*"}],
    )

    packet = Ether(RAW_DHCP_RENEWAL)

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)
        # Ensure no change is ignored
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.1.120",
        dhcp.HOSTNAME: "irobot-ae9ec12dd3b04885bcbfa36afb01e1cc",
        dhcp.MAC_ADDRESS: "50147903852c",
    }


async def test_dhcp_match_hostname(hass):
    """Test matching based on hostname only."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "hostname": "connect"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_dhcp_match_macaddress(hass):
    """Test matching based on macaddress only."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "macaddress": "B8B7F1*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_dhcp_nomatch(hass):
    """Test not matching based on macaddress only."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "macaddress": "ABC123*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_dhcp_nomatch_hostname(hass):
    """Test not matching based on hostname only."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_dhcp_nomatch_non_dhcp_packet(hass):
    """Test matching does not throw on a non-dhcp packet."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(b"")

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_dhcp_nomatch_non_dhcp_request_packet(hass):
    """Test nothing happens with the wrong message-type."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    packet[DHCP].options = [
        ("message-type", 4),
        ("max_dhcp_size", 1500),
        ("requested_addr", "192.168.210.56"),
        ("server_id", "192.168.208.1"),
        ("param_req_list", [1, 3, 28, 6]),
        ("hostname", b"connect"),
    ]

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_dhcp_invalid_hostname(hass):
    """Test we ignore invalid hostnames."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    packet[DHCP].options = [
        ("message-type", 3),
        ("max_dhcp_size", 1500),
        ("requested_addr", "192.168.210.56"),
        ("server_id", "192.168.208.1"),
        ("param_req_list", [1, 3, 28, 6]),
        ("hostname", "connect"),
    ]

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_dhcp_missing_hostname(hass):
    """Test we ignore missing hostnames."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    packet[DHCP].options = [
        ("message-type", 3),
        ("max_dhcp_size", 1500),
        ("requested_addr", "192.168.210.56"),
        ("server_id", "192.168.208.1"),
        ("param_req_list", [1, 3, 28, 6]),
        ("hostname", None),
    ]

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_dhcp_invalid_option(hass):
    """Test we ignore invalid hostname option."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    packet[DHCP].options = [
        ("message-type", 3),
        ("max_dhcp_size", 1500),
        ("requested_addr", "192.168.208.55"),
        ("server_id", "192.168.208.1"),
        ("param_req_list", [1, 3, 28, 6]),
        ("hostname"),
    ]

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_setup_and_stop(hass):
    """Test we can setup and stop."""

    assert await async_setup_component(
        hass,
        dhcp.DOMAIN,
        {},
    )
    await hass.async_block_till_done()

    with patch("homeassistant.components.dhcp.AsyncSniffer.start") as start_call, patch(
        "homeassistant.components.dhcp._verify_l2socket_setup",
    ), patch("homeassistant.components.dhcp.compile_filter",), patch(
        "homeassistant.components.dhcp.DiscoverHosts.async_discover"
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    start_call.assert_called_once()


async def test_setup_fails_as_root(hass, caplog):
    """Test we handle sniff setup failing as root."""

    assert await async_setup_component(
        hass,
        dhcp.DOMAIN,
        {},
    )
    await hass.async_block_till_done()

    wait_event = threading.Event()

    with patch("os.geteuid", return_value=0), patch(
        "homeassistant.components.dhcp._verify_l2socket_setup",
        side_effect=Scapy_Exception,
    ), patch("homeassistant.components.dhcp.DiscoverHosts.async_discover"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    wait_event.set()
    assert "Cannot watch for dhcp packets" in caplog.text


async def test_setup_fails_non_root(hass, caplog):
    """Test we handle sniff setup failing as non-root."""

    assert await async_setup_component(
        hass,
        dhcp.DOMAIN,
        {},
    )
    await hass.async_block_till_done()

    with patch("os.geteuid", return_value=10), patch(
        "homeassistant.components.dhcp._verify_l2socket_setup",
        side_effect=Scapy_Exception,
    ), patch("homeassistant.components.dhcp.DiscoverHosts.async_discover"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert "Cannot watch for dhcp packets without root or CAP_NET_RAW" in caplog.text


async def test_setup_fails_with_broken_libpcap(hass, caplog):
    """Test we abort if libpcap is missing or broken."""

    assert await async_setup_component(
        hass,
        dhcp.DOMAIN,
        {},
    )
    await hass.async_block_till_done()

    with patch("homeassistant.components.dhcp._verify_l2socket_setup",), patch(
        "homeassistant.components.dhcp.compile_filter",
        side_effect=ImportError,
    ) as compile_filter, patch(
        "homeassistant.components.dhcp.AsyncSniffer",
    ) as async_sniffer, patch(
        "homeassistant.components.dhcp.DiscoverHosts.async_discover"
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert compile_filter.called
    assert not async_sniffer.called
    assert (
        "Cannot watch for dhcp packets without a functional packet filter"
        in caplog.text
    )


async def test_device_tracker_hostname_and_macaddress_exists_before_start(hass):
    """Test matching based on hostname and macaddress before start."""
    hass.states.async_set(
        "device_tracker.august_connect",
        STATE_HOME,
        {
            ATTR_HOST_NAME: "Connect",
            ATTR_IP: "192.168.210.56",
            ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER,
            ATTR_MAC: "B8:B7:F1:6D:B5:33",
        },
    )

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        device_tracker_watcher = dhcp.DeviceTrackerWatcher(
            hass,
            {},
            [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_device_tracker_hostname_and_macaddress_after_start(hass):
    """Test matching based on hostname and macaddress after start."""

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        device_tracker_watcher = dhcp.DeviceTrackerWatcher(
            hass,
            {},
            [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()
        hass.states.async_set(
            "device_tracker.august_connect",
            STATE_HOME,
            {
                ATTR_HOST_NAME: "Connect",
                ATTR_IP: "192.168.210.56",
                ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER,
                ATTR_MAC: "B8:B7:F1:6D:B5:33",
            },
        )
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_device_tracker_hostname_and_macaddress_after_start_not_home(hass):
    """Test matching based on hostname and macaddress after start but not home."""

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        device_tracker_watcher = dhcp.DeviceTrackerWatcher(
            hass,
            {},
            [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()
        hass.states.async_set(
            "device_tracker.august_connect",
            STATE_NOT_HOME,
            {
                ATTR_HOST_NAME: "connect",
                ATTR_IP: "192.168.210.56",
                ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER,
                ATTR_MAC: "B8:B7:F1:6D:B5:33",
            },
        )
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 0


async def test_device_tracker_hostname_and_macaddress_after_start_not_router(hass):
    """Test matching based on hostname and macaddress after start but not router."""

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        device_tracker_watcher = dhcp.DeviceTrackerWatcher(
            hass,
            {},
            [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()
        hass.states.async_set(
            "device_tracker.august_connect",
            STATE_HOME,
            {
                ATTR_HOST_NAME: "connect",
                ATTR_IP: "192.168.210.56",
                ATTR_SOURCE_TYPE: "something_else",
                ATTR_MAC: "B8:B7:F1:6D:B5:33",
            },
        )
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 0


async def test_device_tracker_hostname_and_macaddress_after_start_hostname_missing(
    hass,
):
    """Test matching based on hostname and macaddress after start but missing hostname."""

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        device_tracker_watcher = dhcp.DeviceTrackerWatcher(
            hass,
            {},
            [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()
        hass.states.async_set(
            "device_tracker.august_connect",
            STATE_HOME,
            {
                ATTR_IP: "192.168.210.56",
                ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER,
                ATTR_MAC: "B8:B7:F1:6D:B5:33",
            },
        )
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 0


async def test_device_tracker_ignore_self_assigned_ips_before_start(hass):
    """Test matching ignores self assigned ip address."""
    hass.states.async_set(
        "device_tracker.august_connect",
        STATE_HOME,
        {
            ATTR_HOST_NAME: "connect",
            ATTR_IP: "169.254.210.56",
            ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER,
            ATTR_MAC: "B8:B7:F1:6D:B5:33",
        },
    )

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        device_tracker_watcher = dhcp.DeviceTrackerWatcher(
            hass,
            {},
            [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 0


async def test_aiodiscover_finds_new_hosts(hass):
    """Test aiodiscover finds new host."""
    with patch.object(hass.config_entries.flow, "async_init") as mock_init, patch(
        "homeassistant.components.dhcp.DiscoverHosts.async_discover",
        return_value=[
            {
                dhcp.DISCOVERY_IP_ADDRESS: "192.168.210.56",
                dhcp.DISCOVERY_HOSTNAME: "connect",
                dhcp.DISCOVERY_MAC_ADDRESS: "b8b7f16db533",
            }
        ],
    ):
        device_tracker_watcher = dhcp.NetworkWatcher(
            hass,
            {},
            [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_aiodiscover_does_not_call_again_on_shorter_hostname(hass):
    """Verify longer hostnames generate a new flow but shorter ones do not.

    Some routers will truncate hostnames so we want to accept
    additional discovery where the hostname is longer and then
    reject shorter ones.
    """
    with patch.object(hass.config_entries.flow, "async_init") as mock_init, patch(
        "homeassistant.components.dhcp.DiscoverHosts.async_discover",
        return_value=[
            {
                dhcp.DISCOVERY_IP_ADDRESS: "192.168.210.56",
                dhcp.DISCOVERY_HOSTNAME: "irobot-abc",
                dhcp.DISCOVERY_MAC_ADDRESS: "b8b7f16db533",
            },
            {
                dhcp.DISCOVERY_IP_ADDRESS: "192.168.210.56",
                dhcp.DISCOVERY_HOSTNAME: "irobot-abcdef",
                dhcp.DISCOVERY_MAC_ADDRESS: "b8b7f16db533",
            },
            {
                dhcp.DISCOVERY_IP_ADDRESS: "192.168.210.56",
                dhcp.DISCOVERY_HOSTNAME: "irobot-abc",
                dhcp.DISCOVERY_MAC_ADDRESS: "b8b7f16db533",
            },
        ],
    ):
        device_tracker_watcher = dhcp.NetworkWatcher(
            hass,
            {},
            [
                {
                    "domain": "mock-domain",
                    "hostname": "irobot-*",
                    "macaddress": "B8B7F1*",
                }
            ],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 2
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "irobot-abc",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }
    assert mock_init.mock_calls[1][1][0] == "mock-domain"
    assert mock_init.mock_calls[1][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[1][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "irobot-abcdef",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_aiodiscover_finds_new_hosts_after_interval(hass):
    """Test aiodiscover finds new host after interval."""
    with patch.object(hass.config_entries.flow, "async_init") as mock_init, patch(
        "homeassistant.components.dhcp.DiscoverHosts.async_discover",
        return_value=[],
    ):
        device_tracker_watcher = dhcp.NetworkWatcher(
            hass,
            {},
            [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
        )
        await device_tracker_watcher.async_start()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 0

    with patch.object(hass.config_entries.flow, "async_init") as mock_init, patch(
        "homeassistant.components.dhcp.DiscoverHosts.async_discover",
        return_value=[
            {
                dhcp.DISCOVERY_IP_ADDRESS: "192.168.210.56",
                dhcp.DISCOVERY_HOSTNAME: "connect",
                dhcp.DISCOVERY_MAC_ADDRESS: "b8b7f16db533",
            }
        ],
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(minutes=65))
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {
        "source": config_entries.SOURCE_DHCP
    }
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }
