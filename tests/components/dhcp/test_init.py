"""Test the DHCP discovery integration."""
import threading
from unittest.mock import patch

from scapy.error import Scapy_Exception
from scapy.layers.dhcp import DHCP
from scapy.layers.l2 import Ether

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
        {},
        [{"domain": "mock-domain", "hostname": "connect", "macaddress": "B8B7F1*"}],
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)
        # Ensure no change is ignored
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
        hass, {}, [{"domain": "mock-domain", "hostname": "connect"}]
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
        hass, {}, [{"domain": "mock-domain", "macaddress": "B8B7F1*"}]
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
        hass, {}, [{"domain": "mock-domain", "macaddress": "ABC123*"}]
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
        hass, {}, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(RAW_DHCP_REQUEST)

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
        dhcp_watcher.handle_dhcp_packet(packet)

    assert len(mock_init.mock_calls) == 0


async def test_dhcp_nomatch_non_dhcp_packet(hass):
    """Test matching does not throw on a non-dhcp packet."""
    dhcp_watcher = dhcp.DHCPWatcher(
        hass, {}, [{"domain": "mock-domain", "hostname": "nomatch*"}]
    )

    packet = Ether(b"")

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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
        "homeassistant.components.dhcp._verify_l2socket_creation_permission",
    ), patch(
        "homeassistant.components.dhcp.compile_filter",
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
        "homeassistant.components.dhcp._verify_l2socket_creation_permission",
        side_effect=Scapy_Exception,
    ):
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
        "homeassistant.components.dhcp._verify_l2socket_creation_permission",
        side_effect=Scapy_Exception,
    ):
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

    with patch(
        "homeassistant.components.dhcp._verify_l2socket_creation_permission",
    ), patch(
        "homeassistant.components.dhcp.compile_filter",
        side_effect=ImportError,
    ) as compile_filter, patch(
        "homeassistant.components.dhcp.AsyncSniffer",
    ) as async_sniffer:
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
            ATTR_HOST_NAME: "connect",
            ATTR_IP: "192.168.210.56",
            ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER,
            ATTR_MAC: "B8:B7:F1:6D:B5:33",
        },
    )

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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
    assert mock_init.mock_calls[0][2]["context"] == {"source": "dhcp"}
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_device_tracker_hostname_and_macaddress_after_start(hass):
    """Test matching based on hostname and macaddress after start."""

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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
                ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER,
                ATTR_MAC: "B8:B7:F1:6D:B5:33",
            },
        )
        await hass.async_block_till_done()
        await device_tracker_watcher.async_stop()
        await hass.async_block_till_done()

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][1][0] == "mock-domain"
    assert mock_init.mock_calls[0][2]["context"] == {"source": "dhcp"}
    assert mock_init.mock_calls[0][2]["data"] == {
        dhcp.IP_ADDRESS: "192.168.210.56",
        dhcp.HOSTNAME: "connect",
        dhcp.MAC_ADDRESS: "b8b7f16db533",
    }


async def test_device_tracker_hostname_and_macaddress_after_start_not_home(hass):
    """Test matching based on hostname and macaddress after start but not home."""

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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

    with patch.object(
        hass.config_entries.flow, "async_init", return_value=mock_coro()
    ) as mock_init:
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
